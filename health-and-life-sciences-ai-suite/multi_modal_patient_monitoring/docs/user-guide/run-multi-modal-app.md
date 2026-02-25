# Run Multi-Modal Patient Monitoring app (Local Build)

This section provides step‑by‑step instructions for setting up dependencies, running the Health‑AI‑Suite using local Docker images, and stopping the application stack.

**Step1: Initialize MDPnP submodules and dependencies**

This command initializes and updates the MDPnP (Medical Device Plug‑and‑Play) submodules required by the Health‑AI‑Suite.

```

make init-mdpnp

# Run the full Health-AI-Suite using locally built images

```

**Step 2: Run the Health‑AI‑Suite Using Local Images**

This command builds and launches the complete Health‑AI‑Suite stack using locally built Docker images.

```

# Set REGISTRY=false to avoid pulling images from a remote registry

make run REGISTRY=false

```

**Step3: Stop and Clean Up**
This command stops and removes all containers started by the Health‑AI‑Suite.

```
# Stop and clean up all running containers

make down
```


For detailed information about system requirements, architecture, and how the application works, see the  [Full Documentation](docs/user-guide/index.md)

