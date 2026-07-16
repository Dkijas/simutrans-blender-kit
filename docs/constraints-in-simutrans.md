# How Simutrans couples vehicles

Read before touching `core/consists.py`. Everything here is read off the engine
(124.5.1), and every claim names the line.

## The one function that decides everything

`descriptor/vehicle_desc.h:219`:

```cpp
bool can_follow(const vehicle_desc_t *prev_veh) const
{
    if( leader_count==0 ) {
        return true;                                   // no Constraint[Prev] at all
    }
    for( uint8 i=0; i<leader_count; i++ ) {
        vehicle_desc_t const* const veh = get_child<vehicle_desc_t>(6 + i);
        if( veh==prev_veh ) {
            return true;                               // listed explicitly
        }
        if( prev_veh!=NULL  &&  veh==vehicle_desc_t::any_vehicle ) {
            return true;                               // "any" - and note the guard
        }
    }
    return false;
}
```

`can_lead` (`:198`) is the same shape for `Constraint[Next]`.

**`prev_veh == NULL` means "nothing in front of me" — I am at the head.** That is
the whole trick, and everything below falls out of it.

## The three ways to spell a constraint

`vehicle_writer.cc:271` turns `none` into an empty xref, which resolves to a
**NULL child**:

```cpp
// Constraints for previous vehicles, "none" means only suitable at front of an convoi
if (!STRICMP(str.c_str(), "none")) {
    str = "";
}
```

and `pakset_manager.cc:238` makes `any` a **real sentinel object**, registered
under that name:

```cpp
// vehicle to follow to mark something cannot lead a convoi (prev[0]=any) or cannot end a convoi (next[0]=any)
vehicle_desc_t::any_vehicle = new vehicle_desc_t(ignore_wt, 1, vehicle_desc_t::unknown);
obj_for_xref( obj_vehicle, "any", vehicle_desc_t::any_vehicle );
```

So `none` is NULL and `any` is a real pointer, and they are genuinely different
things. (Worth checking rather than assuming: `vehicle_desc.cc:12` initialises
`any_vehicle = NULL`, and if nothing reassigned it, `veh==any_vehicle` would be
`NULL==NULL` and `none` would silently behave as `any` — the exact inversion of its
meaning. `pakset_manager.cc:242` is what makes that not so.)

| Written | Child | `can_follow(NULL)` — at the head | `can_follow(X)` — behind X |
|---|---|---|---|
| *(nothing)* | — | **true** | **true** |
| `none` | NULL | **true** (`NULL==NULL`) | false |
| `any` | sentinel | **false** (the `prev_veh!=NULL` guard) | **true** |
| `Foo` | Foo | false | true iff X is Foo |

## The vocabulary that falls out

This is what the Consist Manager generates, and every line of it is the table
above read sideways:

| What the artist means | Constraint[Prev] | Constraint[Next] |
|---|---|---|
| couples to anything, anywhere | *(omit)* | *(omit)* |
| **only at the head** | `none` | |
| **only at the tail** | | `none` |
| **runs alone, never coupled** | `none` | `none` |
| **never leads** (must have something in front) | `any` | |
| **never ends** (must have something behind) | | `any` |
| **middle only** | `any` | `any` |
| only behind Foo | `Foo` | |
| head, or behind Foo | `none`, `Foo` | |

**`any` is how you say "middle only".** That is not obvious and it is the reverse
of how the word reads: `any` does not mean "anything is allowed", it means "any
*real* vehicle" — and *real* excludes the head, because the head's `prev_veh` is
NULL and the guard rejects it.

## Two things this repo got wrong, found by reading the above

**`addon/ui.py` said a lone `none` means the vehicle "can ONLY ever run alone".**
It does not. `none` in Prev means **only at the head**; running alone needs `none`
on *both* sides. `core/datgen.py` had it right in the same repo — "Write both
`none`s and the vehicle can only ever run ALONE" — so the two files contradicted
each other, and the wrong one was the tooltip an artist reads.

The Civia settles it: `civia465_cab_a` ships `Constraint[Prev][0]=none` **and**
`Constraint[Next][0]=CiviaS465_Int1`. It leads a five-car train. It does not run
alone.

**`core/datgen.py` described `any` as "anything at all".** Half true and
dangerously incomplete: it omits that `any` *forbids* the head. An artist told
"any = anything at all" would use it for a carriage that may go anywhere, and
would get a carriage the game refuses to put at the front of a train — with
nothing warning, because the pak compiles and loads.

## The canonical source

`core/datgen.py`'s `vehicle_dat(constraint_prev=(), constraint_next=())` is what
the `.dat` — and therefore the writer, and therefore the engine — actually reads.

So `core/consists.py` **generates those tuples and nothing else**. It is not a
second representation of coupling that has to be kept in step with the first; it
is a declarative front end that computes the argument `datgen` already takes.
There is one place a constraint is written, and it is the one that was there
before this phase.

## A vehicle's constraints are a UNION

The part that makes a manager worth having rather than a formatter.

A vehicle appearing in more than one consist must allow every neighbour any of
them gives it. A metro motor car that sits behind a cab in the 4-car formation and
behind a trailer in the 6-car one needs **both** in its `Constraint[Prev]` — and
writing that by hand, per vehicle, across two formations, is exactly the
bookkeeping people get wrong.

Miss one and the game does not complain: it simply refuses to let the artist build
their own train in the depot, with no message that says why.
