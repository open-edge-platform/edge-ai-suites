# PPE-compliance stack with a GPU detector and a classifier

Build an end-to-end stack in `./ppe-compliance-stack/` for the industrial
vertical. Object of interest: `hardhat`. Use a detector plus a secondary
classifier (`gvaclassify`) to distinguish compliant vs non-compliant workers,
running on Intel **GPU** (`_gpu` pipeline variant). Filter to the hardhat/vest
class IDs in Node-RED, alert when `count<1 in 15s aggregate` (a worker without
PPE), and publish to `alerts/hardhat` and `stats/hardhat_count`. Include the
`group_add` for `video`/`render` GIDs and pinned image tags, and validate the
`.env` before install.
