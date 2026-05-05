<!--hide_directive
```{eval-rst}
:orphan:
```
hide_directive-->

(model-pi0)=

# General-purpose robot foundation model (Pi0)

Pi0 created by Physical Intelligence introduces a groundbreaking robotic model designed to integrate vision, language, and action (VLA) for general-purpose robotic tasks.

![pi0](../assets/images/pi0.png)

**Model Architecture:**

- A larger VLM backbone with weights initialized from PaliGemma that is pre-trained from large-scale Internet pre-training.
- A smaller action expert (Diffusion Transformer) addresses robot states and generates actions.

**More Information:**

- Full paper: <https://www.pi.website/download/pi0.pdf>
- Homepage: <https://www.pi.website/blog/pi0>
- Github link: <https://github.com/Physical-Intelligence/openpi>

## Model Conversion
