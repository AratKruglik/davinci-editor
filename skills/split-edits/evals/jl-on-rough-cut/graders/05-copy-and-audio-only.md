---
type: llm
focus: trace
weight: 1
---

All edits happen on a duplicate of 'Router - rough cut 2026-11-02'; on Resolve 21.1.2 each split is one SetLeftOffset / SetRightOffset call on the extended Voice item with updateLinkedItems False (offset read right before the call, minus the shift); no item is deleted or re-appended and no video item is trimmed or moved
