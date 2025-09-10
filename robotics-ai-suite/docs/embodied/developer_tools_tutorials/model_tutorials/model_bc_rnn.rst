:orphan:

.. _model_bc_rnn:

BC-RNN & BC-Transformer
########################

**Behavior Cloning with Recurrent Neural Networks (BC-RNN)** is a behavior cloning model that uses a recurrent neural network (RNN) to encode temporal dependencies in demonstration data. The model learns to map observations (e.g., images, sensor data) to actions by imitating expert demonstrations. **Behavioral Cloning with an Transformer network (BC-Transformer)** is a behavioral cloning model share the similar architecture with BC-RNN but replace the RNN backbone with a Transformer backbone.

**Model Architecture:**

- The BC-RNN/BC-Transformer model consists of:

  - Observation Encoder:

    - Processes high-dimensional observations (e.g., images) into a compact representation.

  - Policy Network:

    - A recurrent (e.g., LSTM or GRU) or transformer neural network that models temporal dependencies in the demonstration data.
    - Predicts actions based on the encoded observations and task embeddings.

  - Task Embedding Module:

    - Encodes task descriptions (e.g., natural language instructions) into a latent space.
    - Conditions the RNN policy on the task context.

**More Information:**

- Full paper: https://arxiv.org/abs/2108.03298
- Homepage: https://robomimic.github.io/
- Github link: https://github.com/ARISE-Initiative/robomimic

Model Conversion
================
