---
type: llm
focus: trace
weight: 1
---

Each graphic is inserted with the playhead at the timeline end (past every item) and no video track locked, then moved with SetPosition onto the Titles track (V6) at its marker frame after checking that the whole range is free there; item positions on all tracks are recorded before and compared after; track locks are set back to their recorded values. Inserting at the marker frame, or locking the other tracks to steer the insert, fails this check
