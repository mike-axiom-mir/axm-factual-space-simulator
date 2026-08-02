# Room Interaction Rules v1

Room interactions must declare a truth class.

Allowed classes include:

- calculation from supplied state;
- bounded engineering estimate;
- bounded simulation model;
- transparent evidence heuristic;
- test plan;
- resource-constrained fabrication;
- inventory and provenance;
- time and self-report.

Every interaction stores:

- inputs;
- result;
- truth class;
- claim limit;
- room;
- expedition time;
- previous interaction hash;
- interaction hash.

A room interaction may organize evidence or calculate a margin. It may not manufacture proof.

Fabricated objects grant no capability unless a separate validation receipt exists.
