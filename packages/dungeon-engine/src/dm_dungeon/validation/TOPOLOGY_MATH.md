# Dungeon Topology: Graph Theory, Progression, and Physical Realizability

This document lives beside [`topology.py`](topology.py), the deterministic topology
validator. It explains the mathematics represented by that module, introduces terms as
they become useful, and marks the boundary between what the current validator proves
and what the constructive V1 topology/layout work must prove next.

## 1. What “topology” means here

In mathematics, **topology** broadly studies properties preserved by continuous
deformation: stretching and bending are allowed, while cutting and gluing are not. A
coffee mug and a torus are the standard informal example because each has one hole.

This package uses a discrete, graph-theoretic version of that idea. Before rooms have
coordinates, exact dimensions, or rendered walls, we care about properties that should
not change when a map is stretched or rearranged:

- which rooms are connected;
- whether one room can be reached from another;
- whether a route forms a loop;
- whether removing a room or connection breaks a route;
- whether a key or clue can be acquired before its gate;
- whether a secret route really bypasses what it claims to bypass.

Those are **topological** properties of the dungeon. Room overlap, wall alignment,
corridor width, and grid bounds are later **geometric** properties.

A topology-valid graph is not automatically physically drawable under every map rule.
The distinction is essential:

```text
creative plan -> graph topology -> physical embedding -> exact grid geometry
```

`topology.py` validates the graph and progression semantics. Layout and geometry code
must separately prove or construct the physical embedding.

## 2. Rooms and connections form a graph

A graph is conventionally written

```text
G = (V, E)
```

where:

- `V` is the set of **vertices** (also called nodes);
- `E` is the set of **edges** connecting pairs of vertices.

For a dungeon:

- each `TopologyRoom` is a vertex;
- each corridor, door, stair, or vertical link is an edge;
- floors and connection kinds are labels on vertices/edges, not separate notions of
  connectivity.

Most dungeon movement is treated as **undirected**: if room `a` connects to room `b`,
the adjacency graph contains both `a -> b` and `b -> a`. Directional discovery or
publication can differ by endpoint, but ordinary physical traversal is currently
symmetric after discovery/unlocking.

The contracts can semantically contain multiple distinct connection IDs between the
same pair of rooms. That is a **multigraph** view. `_build_adjacency()` projects it to a
simple adjacency relation for reachability:

```python
Adjacency = dict[str, set[str]]
```

The set removes duplicate neighbors. Connection-sensitive operations, such as closing a
specific gate edge or removing one chokepoint connection, still filter by connection ID
before building that projection. If a parallel connection remains, the two rooms remain
adjacent—as they should.

## 3. References establish a well-defined graph

Before graph algorithms are meaningful, every edge endpoint must identify an existing
vertex. `_validate_references_and_connection_kinds()` checks this **incidence relation**:
which vertices each edge touches.

It also rejects a **self-loop** (`from_room_id == to_room_id`). Self-loops are legitimate
objects in graph theory, but they do not create useful room-to-room traversal here and
would make several dungeon semantics ambiguous.

Connection labels impose additional invariants:

- corridors and doors join rooms on one floor;
- stairs and vertical links join distinct floors whose IDs agree with their endpoint
  rooms.

These checks do not prove connectivity. They prove that the graph is well-formed enough
for connectivity questions to have a precise answer.

## 4. Adjacency, walks, paths, and reachability

Two vertices are **adjacent** when an edge joins them. An adjacency map stores each
vertex's neighbors.

A **walk** is a sequence of vertices where each consecutive pair is adjacent. Vertices
may repeat. A **path** usually means a walk without repeated vertices. For the yes/no
question “can the party get there?”, repeated vertices do not matter: if any walk
exists, a simple path also exists after removing cycles.

`_reachable()` computes the set of vertices reachable from one or more starts using
**breadth-first search** (BFS):

1. mark each valid start visited;
2. place starts in a queue;
3. repeatedly remove one queued vertex;
4. visit every unvisited neighbor and add it to the queue;
5. stop when the queue is empty.

For adjacency-list storage, BFS takes

```text
O(|V| + |E|)
```

time and `O(|V|)` additional memory. Here `|V|` means room count and `|E|` means
connection count.

The implementation sorts starts and neighbors. Sorting is not mathematically necessary,
but it makes traversal deterministic and therefore keeps diagnostics and replay stable.

## 5. Connected components and required-room reachability

A **connected component** is a maximal set of vertices where every pair has a path
between them. An undirected graph is **connected** when it has exactly one component.

The current validator asks a slightly more product-specific question:

- is every required room reachable from at least one entrance?
- can every required room reach at least one exit?

It computes the union of components reached from entrances and exits. In an undirected
graph, “reachable from an exit” and “can reach an exit” are equivalent.

Optional rooms may live outside those required reachability sets. The compiler should
normally make optional content reachable too, but `required=False` means its isolation
does not by itself invalidate required progression.

The topology contract currently permits multiple entrances/exits; the validator requires
at least one of each. A narrower creative compiler may impose exactly one entrance and
one final objective for Tier A.

## 6. Trees, cycles, and loop rank

A **cycle** is a closed path. A **simple cycle** repeats no vertex except the first/last
closure.

`_validate_loop_requirements()` checks a declared ordered room sequence:

```text
(v0, v1, ..., vk-1)
```

It requires:

- all listed vertices are distinct;
- every consecutive pair is adjacent;
- the final vertex is adjacent to the first.

That is a concrete **cycle witness**: the declaration does not merely claim a loop; it
names one.

A connected acyclic graph is a **tree**. A tree with `|V|` vertices has exactly
`|V| - 1` edges. For a graph with `C` connected components, the dimension of its cycle
space—also called **cycle rank**, **circuit rank**, or first Betti number—is

```text
μ = |E| - |V| + C
```

For a connected dungeon:

```text
μ = |E| - |V| + 1
```

Interpretation:

- `μ = 0`: no independent loops; the graph is a tree;
- `μ = 1`: one independent loop;
- each edge added between already-connected vertices increases `μ` by one.

For this equation, `|E|` counts semantic connection IDs, including parallel edges. Two
parallel edges form a length-two cycle in multigraph theory, but the current
`LoopRequirement` requires at least three rooms and cannot witness that cycle. The V1
compiler should either prohibit duplicate room-pair edges in its supported grammar or
represent that case explicitly rather than mixing the multigraph rank with simple-cycle
claims.

The current validator checks explicit loop witnesses but does not yet certify that the
number of requested independent loops equals `μ`. The planned `TopologyCertificate`
should record both the rank and witnesses so validators can recompute them.

## 7. Branches and vertex degree

The **degree** of a vertex is the number of incident edges (or distinct neighbors in the
simple adjacency projection).

A junction with degree three or greater often reads as a branch, but degree alone does
not identify which destinations a design requested. `_validate_branch_requirements()`
therefore checks an explicit local witness:

- branch destinations are distinct;
- each declared destination is directly adjacent to the declared junction.

This contract currently models a star-shaped branch at one junction, not an arbitrary
multi-room branch path. The constructive V1 grammar will represent an attached ordered
path and compile it into exact edges before applying lower-level validation.

## 8. Chokepoints, cut vertices, and bridges

A **cut vertex** (articulation point) is a vertex whose removal increases the number of
connected components. A **bridge** (cut edge) is an edge whose removal does the same.

Dungeon requirements are often more specific: “this room or door must separate room
`s` from room `t`.” That component need not disconnect the entire graph; it only needs
to be an **`s`–`t` separator**.

`_validate_chokepoint_requirements()` uses the definition directly:

```text
s and t are connected in G
and
s and t are disconnected in G - x
```

where `x` is the requested room or connection. For a room, `G - x` removes the vertex
and all incident edges. For a connection, `G - x` removes only that edge ID.

This remove-and-reachability implementation is simple and correct for the small dungeon
graphs in scope. Algorithms such as Tarjan's articulation-point/bridge algorithm can
find all global cut components in `O(|V| + |E|)`, but are unnecessary unless profiling
or broader certificate generation requires them.

## 9. Secret bypasses as constrained subgraphs

A `SecretBypass` names:

- an entry room;
- an exit room;
- the exact connections belonging to the bypass;
- gates it is intended to avoid.

The validator builds a **subgraph** containing only the named bypass edges, then removes
connections blocked by the bypassed gates. It requires a path between bypass entry and
exit in the remaining subgraph.

In symbols, if `B ⊆ E` is the bypass edge set and `X ⊆ E` contains edges blocked by the
named gates, the test is reachability in

```text
G_B = (V, B \ X)
```

The validator separately requires every bypass edge to be DM-only. Visibility is not a
graph-theoretic property; it is product metadata attached to the witness. Both facts are
needed: a route that is hidden but disconnected is not a bypass, and a connected route
that is player-safe is not secret.

## 10. Gates create a second, directed graph

Room traversal is undirected, but gate prerequisites are directional. If gate `a`
requires gate `b`, then `a` depends on `b`; reversing that arrow changes progression.

The gate dependency graph is therefore a directed graph

```text
D = (Gates, prerequisite edges)
```

Keys and clues are terminal resources located in rooms. Gate-to-gate dependencies form
the directed portion that can contain dependency cycles.

### Strongly connected components

A **strongly connected component** (SCC) of a directed graph is a maximal set where
every vertex can reach every other vertex following arrow direction.

A directed cycle exists exactly when an SCC:

- contains more than one vertex; or
- contains one vertex with an edge to itself.

`_strongly_connected_gate_cycles()` implements Tarjan's SCC algorithm. It gives each
vertex a discovery index and a **low-link** value: the smallest discovery index reachable
through the active depth-first-search stack. When a vertex's low-link equals its own
index, it is the root of one SCC, which is popped from the stack.

Tarjan's algorithm runs in

```text
O(|V_D| + |E_D|)
```

where `V_D` is the set of gates and `E_D` is the set of gate-to-gate prerequisite edges.

A dependency cycle is rejected even if another map route might make a particular gate
irrelevant. The declared prerequisite relation itself is contradictory as an ordering.

## 11. Reciprocity is referential integrity, not reachability

Gate dependencies and resource records store both directions:

- a gate says it requires a key/clue;
- that key/clue says which gate it opens/supports.

`_validate_gate_reciprocity()` requires those declarations to agree. This resembles a
bidirectional foreign-key invariant. It does not prove the resource is reachable; it
prevents two records from assigning different meanings to the same IDs.

## 12. Gate progression as a monotone fixed point

Even an acyclic prerequisite graph can be impossible if a key lies behind its own gate.
`_validate_gate_progression()` combines graph reachability with resource acquisition.

At iteration `i`, maintain sets:

- `R_i`: reachable rooms;
- `K_i`: collected keys;
- `C_i`: collected clues;
- `O_i`: opened gates.

One iteration does this:

1. Build the room graph containing only connections whose blockers are all in `O_i`.
2. Compute `R_(i+1)` by BFS from all entrances.
3. Add keys/clues located in `R_(i+1)` to `K_(i+1)` and `C_(i+1)`.
4. Add every gate whose prerequisites are satisfied to `O_(i+1)`.

This defines a **monotone operator** `F` on finite sets:

```text
S_(i+1) = F(S_i)
```

“Monotone” means the algorithm only adds acquired resources/opened gates; it never
forgets one. Because there are finitely many rooms, keys, clues, and gates, repeated
application must reach a **least fixed point**:

```text
F(S*) = S*
```

The loop stops exactly there. This is not guess-and-check: it is deterministic dataflow
analysis over a finite lattice. A simple upper bound on state-expanding iterations is
the number of resources and gates, although each iteration also recomputes room
reachability.

After convergence:

- any unopened gate is unresolvable from the entrance;
- any required room outside `R*` remains progression-blocked.

Python's `all(())` is true, so a gate with no prerequisites opens during the first
iteration. That means “no prerequisite” is treated as mechanically open. Preparation
readiness may still reject missing narrative/mechanical detail at a higher layer.

### Example

Consider rooms and connections:

```text
entry -- hall -- vault
           |
         study
```

The `hall--vault` connection is locked; its key is in `study`.

- Initially the closed gate allows reachability `{entry, hall, study}`.
- The key is collected in `study`.
- The gate opens.
- Reachability expands to include `vault`.

If the key were inside `vault`, the fixed point would never open the gate, correctly
reporting a progression deadlock.

## 13. What topology validity does not prove

The current validator does **not** prove that a graph has a crossing-free rectangular
layout.

### Planarity

A graph is **planar** if it can be drawn in the plane with edges meeting only at shared
endpoints. For a simple connected planar graph with at least three vertices, Euler's
formula implies

```text
|V| - |E| + |F| = 2
```

and therefore

```text
|E| <= 3|V| - 6
```

This edge bound is necessary, not sufficient. The complete graph `K5` and complete
bipartite graph `K3,3` are the classic nonplanar obstructions. Kuratowski's theorem says
a finite graph is planar exactly when it contains no subdivision of either obstruction.

The current `topology.py` does not perform a planarity test.

### Orthogonal and rectangular realization

Even a planar graph needs additional work to become an orthogonal dungeon:

- corridors need noncrossing channels;
- room boundaries need enough distinct ports;
- bends and clearances consume grid space;
- fixed maximum floor bounds may be too small.

Requiring every connection to be a shared-wall door is stricter still. Not every planar
graph is a rectangle-contact graph. Therefore Tier A treats shared-wall doors as a
constructive geometry choice; a general supported connection can use a corridor with
explicit room-wall openings.

## 14. The constructive V1 proof boundary

The alpha recovery does not begin with arbitrary planar graphs. It uses a bounded
**series/parallel-with-spurs** grammar:

1. An ordered critical path creates a connected backbone.
2. A branch attaches an ordered path to an existing vertex.
3. A loop adds a parallel bypass only under a supported embedding rule.

Series composition places one component after another. Parallel composition provides
alternative routes between common terminals. These constructions preserve planarity.
Spurs model useful dead-end branches.

The first physical embedding assigns:

- critical-path rooms to backbone columns;
- branches to dedicated upper/lower bands;
- loops to reserved interval bands;
- every connection to a reserved corridor channel.

When multiple loop intervals are supported, they must be disjoint or nested. Interleaved
intervals such as

```text
a < c < b < d
```

are rejected before layout because the simple band construction cannot realize both
without a crossing. This is an explicit unsupported graph class, not a random routing
failure.

## 15. Port and room-demand arithmetic

Graph degree becomes physical **port demand**: each incident connection needs an opening
on some room side.

For a rectangular room of width `w` and height `h`, its perimeter in cell-edge units is

```text
P = 2w + 2h
```

If each of `d` ports has opening width `o` and adjacent openings require clearance,
then a necessary capacity bound is

```text
P >= d * o + total separation clearance
```

A constructive certificate should use the stronger side-specific version. If `d_N`
ports are assigned to the north wall, for example, then `w` must fit those openings and
their required separation. Width/height are expanded before room placement until all
assigned sides fit.

Interior demand is separate. If room features reserve blocked cells and encounters need
movement/footprint space, layout must ensure

```text
usable interior cells
    = room interior cells - blocked/reserved cells
    >= required encounter/circulation demand
```

These inequalities connect abstract graph degree and annotations to geometric size.
They are not currently calculated by `topology.py`; they belong in the planned topology
certificate and constructive layout.

## 16. Why validation remains necessary after construction

A constructive proof says a solution exists and specifies how to build it. Independent
validation still catches implementation errors:

- an off-by-one bound;
- an opening on the wrong wall;
- a corridor entering an unrelated room;
- a disconnected raster cell region;
- a gate record attached to the wrong edge;
- a DM-only component leaking into player output.

The intended distinction is:

```text
unsupported plan -> compiler/certificate diagnostic
implementation defect -> validator regression failure
```

A validator failure must not trigger random retries or ask the model to invent a new
graph.

## 17. Map from mathematics to the current code

| Mathematical idea | Current implementation |
| --- | --- |
| Vertex/edge incidence and labels | `_validate_references_and_connection_kinds()` |
| Simple undirected adjacency projection | `_build_adjacency()` |
| BFS reachability/components | `_reachable()`, `_has_path()` |
| Entrance/exit reachability | `_validate_required_room_reachability()` |
| Explicit simple-cycle witness | `_validate_loop_requirements()` |
| Junction adjacency witness | `_validate_branch_requirements()` |
| Pair-specific vertex/edge separator | `_validate_chokepoint_requirements()` |
| Restricted hidden subgraph path | `_validate_secret_bypasses()` |
| Bidirectional dependency integrity | `_validate_gate_reciprocity()` |
| Directed SCC/cycle detection | `_strongly_connected_gate_cycles()` |
| Monotone least-fixed-point progression | `_validate_gate_progression()` |
| Planarity/embedding certificate | not implemented yet; P7-14c/d |
| Port/interior feasibility | not implemented yet; P7-14c/d |

## 18. Properties future changes must preserve

Tests around topology construction should check mathematical properties rather than only
example JSON:

- construction always yields one connected required component;
- adding a branch path preserves connectivity and does not increase cycle rank;
- adding one supported bypass increases cycle rank by one;
- every loop declaration has a valid simple-cycle witness;
- removing a declared chokepoint separates its requested endpoints;
- every gate dependency is reachable before that gate at the least fixed point;
- secret-subgraph filtering preserves declared bypass witnesses;
- IDs/order/seed changes do not change graph invariants;
- every accepted certificate belongs to the supported embedding grammar;
- every supported certificate materializes without topology or geometry validator
  errors.

When `TopologyCertificate` and the V1 compiler land, update this document in the same
change so equations and terminology continue to describe executable behavior rather
than architectural aspiration.
