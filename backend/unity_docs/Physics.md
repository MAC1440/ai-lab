# Unity Physics Reference & Development Guidelines

This document provides architectural standards, performance parameters, and clean code implementation rules for the physics sub-systems in this Unity project.

---

## 🏗️ Core Architecture & Execution Rules

### 1. FixedUpdate vs Update
* **Rule**: All physics calculations, force applications, and velocity adjustments **MUST** happen within `FixedUpdate()`.
* **Reason**: `Update()` runs on a variable framerate. Processing physics there will cause jittery movement, inconsistent jump heights, and broken collision detection due to frame rate dependencies.

### 2. Rigidbody Interaction
* **Rule**: Move `Rigidbody` components via physics forces (`AddForce`, `MovePosition`), **NEVER** by directly modifying `transform.position`.
* **Reason**: Translating transforms teleports the object, breaking continuous collision detection and causing performance overhead as the physics world recalculates statically moved geometry.

---

## ⚡ Performance Optimization Checklist

- [ ] **Primitive Over Mesh**: Use primitive colliders (Box, Sphere, Capsule) instead of `MeshCollider` whenever possible.
- [ ] **Convex Mesh Colliders**: If a `MeshCollider` is required for a moving Rigidbody, check the **Convex** checkbox.
- [ ] **Interpolation Management**: Enable **Interpolation** on the Rigidbody of the main player character and primary camera targets to smooth out visual movement. Keep it disabled (`None`) on standard environmental physics debris.
- [ ] **Layer-Based Collisions**: Configure the **Collision Matrix** (`Edit > Project Settings > Physics`) to disable redundant layer-on-layer collision checks (e.g., UI layers checking against environment layers).
- [ ] **Sleep Thresholds**: Allow inactive objects to sleep naturally. Avoid spamming `Rigidbody.WakeUp()` unless explicitly handling gameplay logic interactions.

---

## 💻 Canonical Scripting Reference

### 1. Applying Forces & Movement
```csharp
using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class PhysicsMovement : MonoBehaviour
{
    [SerializeField] private float speed = 10f;
    [SerializeField] private float jumpForce = 5f;
    
    private Rigidbody rb;
    private Vector3 moveInput;
    private bool isJumpRequested;

    private void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    private void Update()
    {
        // Gather input on frame updates
        moveInput = new Vector3(Input.GetAxis("Horizontal"), 0f, Input.GetAxis("Vertical"));
        
        if (Input.GetButtonDown("Jump"))
        {
            isJumpRequested = true;
        }
    }

    private void FixedUpdate()
    {
        // Continuous movement: Use ForceMode.VelocityChange or Acceleration
        Vector3 targetVelocity = moveInput * speed;
        Vector3 velocityChange = targetVelocity - new Vector3(rb.linearVelocity.x, 0f, rb.linearVelocity.z);
        rb.AddForce(velocityChange, ForceMode.VelocityChange);

        // Discrete push / Instant impulse
        if (isJumpRequested)
        {
            rb.AddForce(Vector3.up * jumpForce, ForceMode.Impulse);
            isJumpRequested = false;
        }
    }
}
```

### 2. Handling Collisions vs Triggers
```csharp
using UnityEngine;

public class PhysicsInteractions : MonoBehaviour
{
    // Physical Impact: Triggers when colliders physically bump
    private void OnCollisionEnter(Collision collision)
    {
        if (collision.gameObject.CompareTag("Hazard"))
        {
            // Evaluate contact points / Impact force
            float impactForce = collision.relativeVelocity.magnitude;
            Debug.Log(\$"Impact force calculated: {impactForce}");
        }
    }

    // Overlap / Pass-through: Triggers when 'Is Trigger' is enabled
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Collectible"))
        {
            // Execute non-physical event logic
            Destroy(other.gameObject);
        }
    }
}
```

---

## 🛠️ Debugging & Diagnostics

1. **Physics Debugger**: Use `Window > Analysis > Physics Debugger` to check hidden colliders, verify broadphase performance, and visualize layer masks in real-time.
2. **Raycast LayerMasking**: Always pass a clear layer mask explicit bitshift value (`1 << LayerMask.NameToLayer("LayerName")`) into your `Physics.Raycast` or `Physics.OverlapSphere` loops to avoid scanning the entire world geometry.
