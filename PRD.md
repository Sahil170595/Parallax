# Advanced Architecture Supplement: Vision-First UI Capture

**For Distinguished Engineering Review**  
**Alternative/Complementary Approach to Selector-Based Automation**

---

## Executive Summary

Based on cutting-edge research from Skyvern's vision-LLM approach and similar browser automation AI systems, this supplement proposes a **vision-first architecture** that complements or enhances the selector-based system in the main PRD.

### Key Innovation
Instead of relying solely on DOM selectors (which break when UIs change), use **computer vision + LLMs** to understand web pages visually, enabling true generalization across applications.

---

## Why Vision-First Matters

### Traditional Selector Limitations
```python
# This breaks when Linear changes their UI:
button = await page.click('[data-testid="create-project-button"]')

# This ALSO breaks when they change the button text:
button = await page.click('button:has-text("New Project")')
```

### Vision-First Advantage
Computer vision systems can recognize a submit button whether it's styled as a green rectangle, a rounded blue button, or even a custom graphic element by analyzing patterns, colors, shapes, and text positioning.

Skyvern can operate on websites it's never seen before by mapping visual elements to actions necessary to complete a workflow, without any customized code, and is resistant to website layout changes.

---

## Hybrid Architecture: Best of Both Worlds

### Recommended Approach: Dual-Path System

```
┌─────────────────────────────────────────────────────────────┐
│                    Task Input (Agent A)                     │
│        "How do I create a project in Linear?"               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│               LLM Orchestrator (Claude)                     │
│          - Parse task & generate plan                       │
│          - Decide: Selector vs Vision vs Hybrid             │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ↓                 ↓
┌──────────────┐   ┌──────────────┐
│ Selector Path│   │ Vision Path  │
│ (Fast/Cheap) │   │ (Robust/Gen) │
└──────┬───────┘   └───────┬──────┘
       │                   │
       │     ┌─────────────┤
       │     │ Fallback if │
       │     │ selector    │
       │     │ fails       │
       └─────↓─────────────┘
             │
    ┌────────┴─────────┐
    │  Unified Actions │
    │  + Screenshots   │
    └──────────────────┘
```

### Decision Logic
```python
class ActionExecutionStrategy:
    async def execute_action(self, action: Action, page: Page):
        """Execute using best available method"""
        
        # Try selector-based first (faster, cheaper)
        if action.has_reliable_selector():
            try:
                return await self.execute_with_selector(action, page)
            except (TimeoutError, ElementNotFoundError):
                logger.info("Selector failed, falling back to vision")
        
        # Fall back to vision-based approach
        return await self.execute_with_vision(action, page)
```

---

## Vision-Based Implementation

### Component 1: Screenshot Analysis with Vision LLM

```python
class VisionBasedElementLocator:
    """Use vision LLMs to locate elements visually"""
    
    def __init__(self, vision_model="claude-sonnet-4"):
        self.vision_model = vision_model
        self.client = anthropic.Anthropic()
    
    async def find_element(
        self, 
        page: Page, 
        description: str,
        action_type: str = "click"
    ) -> Dict[str, any]:
        """
        Find element using vision analysis instead of selectors
        Returns: {'x': x, 'y': y, 'confidence': 0.95}
        """
        
        # Capture screenshot with element annotations
        screenshot = await self._capture_annotated_screenshot(page)
        
        # Send to vision LLM
        prompt = f"""
        Analyze this webpage screenshot and locate the element described below.
        
        Element description: {description}
        Action to perform: {action_type}
        
        Instructions:
        1. Identify the element that best matches the description
        2. Provide the x,y coordinates of the element's center
        3. Explain your reasoning
        4. Rate your confidence (0-1)
        
        Return JSON format:
        {{
            "element_found": true,
            "x": 500,
            "y": 300,
            "confidence": 0.95,
            "reasoning": "Located blue 'New Project' button in top-right",
            "alternative_elements": [...]
        }}
        """
        
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        result = json.loads(response.content[0].text)
        return result
    
    async def _capture_annotated_screenshot(self, page: Page) -> str:
        """Capture screenshot with interactive elements highlighted"""
        
        # Inject script to highlight clickable elements
        await page.evaluate("""() => {
            // Add visual markers to interactive elements
            document.querySelectorAll(
                'button, a, input, select, [role="button"], [onclick]'
            ).forEach((el, index) => {
                if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                    const rect = el.getBoundingClientRect();
                    const marker = document.createElement('div');
                    marker.style.cssText = `
                        position: fixed;
                        left: ${rect.left}px;
                        top: ${rect.top}px;
                        width: ${rect.width}px;
                        height: ${rect.height}px;
                        border: 2px solid rgba(255, 0, 0, 0.5);
                        pointer-events: none;
                        z-index: 999999;
                        box-sizing: border-box;
                    `;
                    marker.setAttribute('data-element-index', index);
                    document.body.appendChild(marker);
                }
            });
        }""")
        
        # Capture screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        
        # Clean up markers
        await page.evaluate("""() => {
            document.querySelectorAll('[data-element-index]').forEach(el => el.remove());
        }""")
        
        return screenshot_b64
    
    async def click_at_coordinates(self, page: Page, x: int, y: int):
        """Click at specific coordinates (vision-determined)"""
        await page.mouse.click(x, y)
```

### Component 2: Multi-Agent Computer Vision System

Inspired by Skyvern's swarm of agents to comprehend a website and plan and execute actions:

```python
class MultiAgentVisionSystem:
    """
    Multi-agent system for vision-based UI understanding
    Each agent has a specialized role
    """
    
    def __init__(self):
        self.layout_agent = LayoutAnalysisAgent()
        self.element_agent = ElementDetectionAgent()
        self.state_agent = StateUnderstandingAgent()
        self.action_agent = ActionPlanningAgent()
    
    async def analyze_page(self, page: Page, task_context: str):
        """
        Multi-agent analysis of page state
        Returns comprehensive understanding for action planning
        """
        
        # Capture screenshot
        screenshot = await page.screenshot()
        
        # Agent 1: Layout Analysis
        layout = await self.layout_agent.analyze(screenshot)
        # Returns: regions, navigation, content areas, modals
        
        # Agent 2: Element Detection  
        elements = await self.element_agent.detect(screenshot, layout)
        # Returns: buttons, inputs, links with visual properties
        
        # Agent 3: State Understanding
        state = await self.state_agent.understand(
            screenshot, layout, elements, task_context
        )
        # Returns: current workflow stage, what's possible, blockers
        
        # Agent 4: Action Planning
        action = await self.action_agent.plan(
            state, elements, task_context
        )
        # Returns: next action to take with target element
        
        return {
            'layout': layout,
            'elements': elements,
            'state': state,
            'recommended_action': action
        }

class LayoutAnalysisAgent:
    """Understands page structure and regions"""
    
    async def analyze(self, screenshot: bytes) -> dict:
        """
        Identify major page regions:
        - Navigation/header
        - Sidebar
        - Main content area
        - Modals/overlays
        - Footer
        """
        
        prompt = """
        Analyze this webpage layout and identify:
        1. Major regions (navigation, content, modals, etc.)
        2. Visual hierarchy
        3. Active/focused areas
        4. Any overlays or blocking elements
        
        Return structured JSON with bounding boxes.
        """
        
        # Use vision LLM for analysis
        result = await self._query_vision_llm(screenshot, prompt)
        return result

class ElementDetectionAgent:
    """Detects and categorizes interactive elements"""
    
    async def detect(self, screenshot: bytes, layout: dict) -> list:
        """
        Find all interactive elements:
        - Buttons (with text/icons)
        - Form inputs
        - Links
        - Dropdowns
        - Custom controls
        """
        
        prompt = """
        Within the identified content regions, locate all interactive elements.
        
        For each element provide:
        - Type (button, input, link, etc.)
        - Position (x, y, width, height)
        - Visual description
        - Text content
        - State (enabled, focused, selected)
        
        Return as JSON array.
        """
        
        result = await self._query_vision_llm(screenshot, prompt)
        return result

class StateUnderstandingAgent:
    """Understands current workflow state"""
    
    async def understand(
        self, 
        screenshot: bytes,
        layout: dict,
        elements: list,
        task_context: str
    ) -> dict:
        """
        Determine:
        - What page/state are we in?
        - What just happened?
        - What's possible next?
        - Are there blockers (errors, loading)?
        """
        
        prompt = f"""
        Task context: {task_context}
        
        Based on the layout and elements detected, determine:
        1. Current workflow stage
        2. Success/error indicators
        3. Loading states
        4. Available next actions
        5. Any blockers or issues
        
        Consider the task context when interpreting the state.
        """
        
        result = await self._query_vision_llm(screenshot, prompt)
        return result
```

### Component 3: Coordinate-Based Action Execution

```python
class CoordinateBasedExecutor:
    """Execute actions using visual coordinates instead of selectors"""
    
    async def execute_action(
        self, 
        page: Page,
        action: dict
    ) -> bool:
        """
        Execute action using coordinates from vision analysis
        
        action format:
        {
            'type': 'click',
            'coordinates': {'x': 500, 'y': 300},
            'element_description': 'New Project button',
            'confidence': 0.95
        }
        """
        
        action_type = action['type']
        coords = action['coordinates']
        
        if action_type == 'click':
            await page.mouse.click(coords['x'], coords['y'])
        
        elif action_type == 'type':
            # Click input field first
            await page.mouse.click(coords['x'], coords['y'])
            await page.keyboard.type(action['value'])
        
        elif action_type == 'hover':
            await page.mouse.move(coords['x'], coords['y'])
        
        # Wait for page to stabilize after action
        await self._wait_for_stabilization(page)
        
        return True
    
    async def _wait_for_stabilization(self, page: Page, timeout=5000):
        """Wait for page to finish responding to action"""
        
        # Multiple stability indicators
        await asyncio.gather(
            self._wait_for_network_idle(page),
            self._wait_for_animations(page),
            self._wait_for_dom_stable(page)
        )
```

---

## State Capture with Vision Understanding

### Enhanced State Capture

```python
class VisionEnhancedStateCapture:
    """Capture states with deep visual understanding"""
    
    async def capture_state(
        self, 
        page: Page,
        workflow_context: str
    ) -> UIState:
        """Capture state with vision-based analysis"""
        
        # Traditional metadata
        metadata = {
            'url': page.url,
            'title': await page.title(),
            'timestamp': time.time()
        }
        
        # Screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        
        # Vision analysis of screenshot
        vision_analysis = await self._analyze_screenshot(
            screenshot_bytes,
            workflow_context
        )
        
        metadata.update({
            'vision_analysis': vision_analysis,
            'detected_elements': vision_analysis['elements'],
            'workflow_stage': vision_analysis['stage'],
            'user_attention_areas': vision_analysis['focus_areas']
        })
        
        return UIState(
            id=str(uuid.uuid4()),
            screenshots={'desktop': screenshot_bytes},
            metadata=metadata,
            significance=self._determine_significance(vision_analysis)
        )
    
    async def _analyze_screenshot(
        self, 
        screenshot: bytes,
        context: str
    ) -> dict:
        """Use vision LLM to understand what's in the screenshot"""
        
        prompt = f"""
        Workflow context: {context}
        
        Analyze this screenshot and provide:
        
        1. **Workflow Stage**: What stage of the workflow is this?
           (e.g., "Initial list view", "Creation modal open", "Success state")
        
        2. **Key Elements**: What are the most important interactive elements?
           List with descriptions and purposes.
        
        3. **User Intent Signals**: What actions is the user likely to take next?
        
        4. **Visual Focal Points**: Where would a user's attention be drawn?
           (For highlighting in documentation)
        
        5. **State Significance**: Is this a critical state to document?
           (Critical/Supporting/Optional)
        
        6. **Differences from Previous**: What changed from typical previous states?
        
        Return as structured JSON.
        """
        
        # Query vision LLM
        response = await self.vision_llm.analyze(screenshot, prompt)
        return response
```

### Intelligent State Deduplication

```python
class VisionBasedDeduplication:
    """Use vision similarity instead of DOM hashing"""
    
    def __init__(self):
        self.recent_screenshots = []
        self.similarity_threshold = 0.92
    
    async def should_capture_state(
        self, 
        current_screenshot: bytes
    ) -> bool:
        """Determine if state is significantly different from recent ones"""
        
        if not self.recent_screenshots:
            return True
        
        # Compare with recent screenshots using vision
        for prev_screenshot in self.recent_screenshots[-3:]:
            similarity = await self._compute_visual_similarity(
                current_screenshot,
                prev_screenshot
            )
            
            if similarity > self.similarity_threshold:
                logger.debug(f"Skipping similar state (similarity: {similarity})")
                return False
        
        return True
    
    async def _compute_visual_similarity(
        self,
        img1: bytes,
        img2: bytes
    ) -> float:
        """
        Compute perceptual similarity between screenshots
        Options:
        1. Structural Similarity Index (SSIM) - fast, local
        2. Vision LLM comparison - slower, semantic
        3. Perceptual hashing - balanced
        """
        
        # Option 1: Fast perceptual hash (for MVP)
        hash1 = self._perceptual_hash(img1)
        hash2 = self._perceptual_hash(img2)
        
        hamming_distance = bin(hash1 ^ hash2).count('1')
        similarity = 1 - (hamming_distance / 64)  # 64-bit hash
        
        return similarity
    
    def _perceptual_hash(self, image_bytes: bytes) -> int:
        """Compute perceptual hash of image"""
        from PIL import Image
        import imagehash
        
        img = Image.open(io.BytesIO(image_bytes))
        return int(str(imagehash.phash(img)), 16)
```

---

## Advantages of Hybrid Approach

### 1. **Robustness**
- **Selector-based**: Fast when it works
- **Vision-based**: Works when selectors break
- **Combined**: Best reliability

### 2. **Generalization**
Vision approach works across:
- Applications never seen before
- UI redesigns without code changes
- Custom components without standard selectors

### 3. **Rich State Understanding**
Vision LLMs can:
- Understand workflow context semantically
- Identify significant vs trivial states
- Detect completion without hardcoded rules
- Explain what changed and why it matters

### 4. **Cost Optimization**
```python
# Use cheap selector-based when reliable
if action.has_test_id:
    cost_per_action = $0.0001  # DOM query
    
# Fall back to vision when needed
else:
    cost_per_action = $0.02   # Vision LLM call
    
# Hybrid approach: ~90% selector, ~10% vision
average_cost = 0.9 * $0.0001 + 0.1 * $0.02 = $0.002/action
```

---

## Implementation Recommendations

### Phase 1: Start with Selectors (Week 1-2)
Build the selector-based system from main PRD first. It's:
- Faster to implement
- Cheaper to run
- Good for known apps
- Establishes baseline

### Phase 2: Add Vision Fallback (Week 3)
Integrate vision-based element location:
- When selector fails
- For completion detection
- For state significance analysis

### Phase 3: Multi-Agent Enhancement (Future)
If time permits, add multi-agent vision system for:
- Better workflow understanding
- Smarter action planning
- Richer state metadata

---

## Cost-Benefit Analysis

### Selector-Only Approach
**Pros**:
- Fast (~100ms per action)
- Cheap (~$0.0001 per action)
- Deterministic

**Cons**:
- Brittle (breaks on UI changes)
- Requires app-specific selectors
- Limited generalization

### Vision-Only Approach  
**Pros**:
- Truly generalizable
- Handles unknown apps
- Self-healing on UI changes

**Cons**:
- Slow (~2-3s per action)
- Expensive (~$0.02 per action)
- Requires powerful vision models

### Hybrid Approach (Recommended)
**Pros**:
- Fast AND robust
- Cost-effective (~$0.002 per action)
- Graceful degradation
- Best of both worlds

**Cons**:
- More complex implementation
- Need both systems

---

## Code Integration Example

```python
class HybridWorkflowExecutor:
    """Combines selector and vision approaches"""
    
    def __init__(self):
        self.selector_executor = SelectorBasedExecutor()
        self.vision_executor = VisionBasedExecutor()
        self.strategy = "selector_first"  # or "vision_first", "vision_only"
    
    async def execute_workflow(
        self, 
        task: str,
        page: Page
    ) -> Workflow:
        """Execute workflow using hybrid approach"""
        
        # Generate plan (using LLM)
        plan = await self._plan_workflow(task)
        
        workflow = Workflow(task=task)
        
        for step in plan.steps:
            try:
                # Try selector-based first
                if self.strategy == "selector_first":
                    result = await self.selector_executor.execute(step, page)
                else:
                    # Vision-first strategy
                    result = await self.vision_executor.execute(step, page)
                
            except ActionFailedError as e:
                logger.warning(f"Primary strategy failed: {e}, using fallback")
                
                # Fallback to vision
                if self.strategy == "selector_first":
                    result = await self.vision_executor.execute(step, page)
                else:
                    # Fallback to selector
                    result = await self.selector_executor.execute(step, page)
            
            # Capture state after action
            state = await self._capture_state_hybrid(page, step)
            workflow.add_state(state)
            
            # Check completion (vision-based for robustness)
            if await self._is_complete_vision(page, workflow, plan):
                break
        
        return workflow
    
    async def _capture_state_hybrid(
        self, 
        page: Page,
        step: WorkflowStep
    ) -> UIState:
        """Capture state with both traditional and vision metadata"""
        
        # Traditional metadata (fast)
        dom_metadata = await self.selector_executor.get_state_metadata(page)
        
        # Vision analysis (for significance and understanding)
        if step.requires_vision_analysis:
            vision_metadata = await self.vision_executor.analyze_state(
                page, 
                step.context
            )
        else:
            vision_metadata = None
        
        return UIState(
            dom_metadata=dom_metadata,
            vision_metadata=vision_metadata,
            screenshot=await page.screenshot()
        )
```

---

## Recommended Tools & Models

### Vision Models (Ranked by Cost/Performance)

1. **Claude Sonnet 4.5** (Recommended)
   - Excellent vision understanding
   - Strong reasoning
   - $3/$15 per MTok (input/output)
   
2. **Gemini 2.0 Flash**
   - Very fast
   - Cheap ($0.075/$0.30 per MTok)
   - Good for high-volume

3. **GPT-4o**
   - Strong vision capabilities
   - $2.50/$10 per MTok
   - Good alternative

### Computer Vision Libraries

For local/cheap vision tasks:
```python
# Perceptual hashing (similarity)
imagehash==4.3.1

# Image processing
pillow==10.1.0

# Optional: OCR for text extraction
pytesseract==0.3.10
easyocr==1.7.0
```

---

## Testing Vision-Based System

### Test Cases

```python
class TestVisionBasedLocation:
    async def test_find_button_by_visual_description(self):
        """Test finding button using only description"""
        locator = VisionBasedElementLocator()
        
        result = await locator.find_element(
            page=test_page,
            description="blue button with white text that says New Project",
            action_type="click"
        )
        
        assert result['element_found']
        assert result['confidence'] > 0.8
        
        # Verify coordinates are in reasonable range
        assert 0 < result['x'] < test_page.viewport_size['width']
        assert 0 < result['y'] < test_page.viewport_size['height']
    
    async def test_fallback_to_vision_on_selector_failure(self):
        """Test that vision fallback works"""
        executor = HybridWorkflowExecutor()
        
        # Simulate selector failure
        with mock.patch.object(
            executor.selector_executor, 
            'execute',
            side_effect=ElementNotFoundError()
        ):
            result = await executor.execute_workflow(
                "Create a project",
                test_page
            )
            
        # Should complete using vision fallback
        assert result.status == "complete"
```

---

## Conclusion: Recommended Approach

For this take-home assignment, I recommend:

### **Tier 1: Core Deliverable** (80% effort)
Implement the selector-based system from the main PRD:
- Solid Playwright automation
- LLM-driven task planning  
- State detection and capture
- Works reliably on 3-5 workflows

### **Tier 2: Vision Enhancement** (15% effort)
Add vision-based improvements:
- Vision LLM for completion detection
- Screenshot analysis for state significance
- Fallback element location if time permits

### **Tier 3: Future-Proof Documentation** (5% effort)
Document the hybrid architecture:
- Show awareness of vision-first approaches
- Explain when/why to use each method
- Demonstrate distinguished engineering thinking

This demonstrates:
✅ Strong implementation skills (selector system)  
✅ Awareness of cutting-edge techniques (vision)  
✅ Practical engineering judgment (hybrid approach)  
✅ Scalability thinking (future-proof architecture)

The vision-based approach is the **future** of browser automation, but the selector-based approach is the **pragmatic present** for this assignment's scope.