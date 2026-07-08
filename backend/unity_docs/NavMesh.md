# Unity AI Navigation (NavMesh) Guide

This document covers the core setup, components, and scripting references for implementing Pathfinding and AI Navigation within Unity using the native **AI Navigation** package.

## 📦 1. Installation

Modern versions of Unity manage the Navigation mesh system via the Package Manager.

1. Open **Window > Package Manager** in the top menu.
2. Select **Packages: Unity Registry**.
3. Search for **AI Navigation** and click **Install**.

---

## 🏗️ 2. Core Components

The Navigation system relies on four primary high-level components to map out the environment and drive entities:

*   **NavMeshSurface**: Defines the walkable region for a specific Agent type. Place this on a parent layout or environment manager GameObject.
*   **NavMeshAgent**: The pathfinding component added to characters/enemies to allow them to move towards a target location.
*   **NavMeshObstacle**: Applied to dynamic objects (like moving crates or closing doors) that need to block paths at runtime.
*   **NavMeshLink**: Connects distinct, disconnected sections of a NavMesh (e.g., creating a bridge to handle jumping or falling gaps).

---

## 🛠️ 3. Environment Setup & Baking

To generate the underlying navigation grid data structure, you must "bake" your scene geometry:

### Step-by-Step Generation
1. Select all environment GameObjects intended for your AI to walk on or collide with.
2. In the **Inspector**, check the box for **Navigation Static** (or add a `NavMeshSurface` component to a root container).
3. Open the baking menu via **Window > AI > Navigation** (or click the Surface component).
4. Configure agent sizing criteria:
    *   **Agent Radius**: Defines how close an agent can get to structural walls.
    *   **Agent Height**: Defines the vertical clearance needed to walk under obstacles.
    *   **Max Slope**: The maximum ramp angle an agent can walk up.
    *   **Step Height**: The maximum height of ledges or steps an agent can climb over.
5. Click **Bake**. 
*(Note: A scene-specific `.asset` file containing the baked grid will generate inside a directory sharing your scene's name.)*

---

## 💻 4. C# Scripting Implementation

To dictate AI movement via code, you must include the `UnityEngine.AI` namespace. Below is a foundational implementation pattern.

### Basic Enemy Movement Script

```csharp
using UnityEngine;
using UnityEngine.AI; // Required for NavMesh components

[RequireComponent(typeof(NavMeshAgent))]
public class EnemyController : MonoBehaviour
{
    [Header("Target Tracking")]
    [SerializeField] private Transform targetTransform;
    [SerializeField] private float updateInterval = 0.2f;

    private NavMeshAgent agent;
    private float nextUpdateTime;

    private void Awake()
    {
        // Cache the reference to the attached NavMeshAgent
        agent = GetComponent<NavMeshAgent>();
    }

    private void Update()
    {
        if (targetTransform == null) return;

        // Throttling path updates optimizes runtime CPU usage
        if (Time.time >= nextUpdateTime)
        {
            nextUpdateTime = Time.time + updateInterval;
            
            // Explicitly command the agent to compute a path to the target location
            agent.SetDestination(targetTransform.position);
        }
    }
}
```

### Essential Scripting API Functions

*   `agent.SetDestination(Vector3 target)`: Instructs the agent to compute and begin following a path to the destination coordinates.
*   `agent.isStopped = true/false`: Halts or resumes movement along the current path immediately.
*   `agent.remainingDistance`: Returns the distance remaining along the active path before reaching the target.
*   `NavMesh.SamplePosition(...)`: Finds the closest valid point on the baked NavMesh grid relative to a raw 3D coordinate vector.
