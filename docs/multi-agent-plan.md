# Fresh Buddy — Multi-Agent Task Assignments

## System Overview

Fresh Buddy gets a multi-agent system where specialized agents work in parallel on different aspects of the project.

## Agent Roles

### 🤖 Orchestrator (Alfredo/Main Agent)
- Coordinates all agents
- Assigns tasks
- Reviews and integrates all work
- Final delivery to Daniel

### 👾 Face Animator Agent
**Session label**: `face-animator`
**Responsibilities**:
- Design and implement 80s futuristic face animations
- Create smooth expression transitions
- Implement easing functions
- Add visual effects (scanlines, glow, bloom)
- Update `expressions.py` with new system

### 💻 Code Agent
**Session label**: `code-agent`
**Responsibilities**:
- Update display driver for animation support
- Enhance preview server with debug controls
- Implement animation timing controller
- Refactor face rendering for layer-based approach
- Ensure architectural consistency

### 🧪 Test Agent
**Session label**: `test-agent`
**Responsibilities**:
- Write comprehensive tests for animation system
- Test expression transitions
- Test easing functions
- Integration tests for face + display
- Ensure all tests pass before review

### 👀 Review Agent
**Session label**: `review-agent`
**Responsibilities**:
- Code quality review of all changes
- Best practices audit
- Performance analysis
- Security review
- Final approval gate

---

## Task Assignments

### Task 1: Face Animation System (Face Animator)
```
Priority: CRITICAL
Deadline: By tomorrow morning
Deliverables:
1. expressions.py updated with 80s style
2. Easing functions implemented
3. Smooth transition system
4. Visual effects (scanlines, glow)
```

### Task 2: Display & Animation Infrastructure (Code Agent)
```
Priority: CRITICAL
Deadline: By tomorrow morning
Deliverables:
1. Animation timing controller in display.py
2. Enhanced preview_server.py
3. Layer-based rendering support
4. Frame rate management
```

### Task 3: Test Suite (Test Agent)
```
Priority: CRITICAL
Deadline: By tomorrow morning
Deliverables:
1. test_expressions.py (animation tests)
2. test_display.py (rendering tests)
3. test_integration.py (end-to-end)
4. All tests passing
```

### Task 4: Code Review (Review Agent)
```
Priority: HIGH
Deadline: After all other tasks complete
Deliverables:
1. Review report
2. Issues list (if any)
3. Approval/rejection decision
```

---

## Communication Protocol

1. **Orchestrator → Agent**: Spawn agent with clear task
2. **Agent → Orchestrator**: Complete task, report results
3. **Orchestrator**: Integrate, test, iterate
4. **Final delivery**: Orchestrator → Daniel

---

## Success Criteria

- [ ] All expressions render correctly in 80s style
- [ ] Expression transitions are smooth (200-400ms, eased)
- [ ] Preview server shows live animation
- [ ] All existing tests pass
- [ ] New animation tests pass
- [ ] Code review approved
- [ ] System is FUNZIONANTE (working) by morning

---

## Agent Spawn Commands

```python
# Face Animator
sessions_spawn(label="face-animator", mode="session", task="...")

# Code Agent
sessions_spawn(label="code-agent", mode="session", task="...")

# Test Agent
sessions_spawn(label="test-agent", mode="session", task="...")

# Review Agent
sessions_spawn(label="review-agent", mode="session", task="...")
```
