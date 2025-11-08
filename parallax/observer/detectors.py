from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from parallax.core.capture import redact_screenshot
from parallax.core.schemas import UIState, RoleNode
from parallax.observer.role_tree import jaccard_similarity


class Detectors:
    def __init__(self, config: Dict[str, Any], vision_analyzer=None) -> None:
        self.config = config
        self._previous_roles: Optional[List[RoleNode]] = None
        self._previous_form_validity: Optional[bool] = None
        self.vision_analyzer = vision_analyzer
        self._task_context: Optional[str] = None
        self._previous_state: Optional[Dict[str, Any]] = None

    def set_task_context(self, task_context: str) -> None:
        """Set task context for vision analysis."""
        self._task_context = task_context
    
    async def capture_state(
        self,
        page,
        action_desc: Optional[str],
        save_dir: Optional[Path],
        index: int,
    ) -> Optional[UIState]:
        url = page.url
        roles = await self._extract_role_tree(page)
        has_modal = any(r.role == "dialog" for r in roles)
        has_toast = await self._detect_toast(page)
        form_validity = await self._check_form_validity(page)
        has_loader = await self._detect_loader(page)
        role_diff = self._compute_role_diff(roles)
        signature = self._hash_signature(url, roles)
        description = self._describe(url, roles, has_toast, form_validity, has_loader, role_diff)
        
        capture_cfg = self.config.get("capture", {})
        multi_viewport = capture_cfg.get("multi_viewport", True)
        # Multi-viewport screenshots
        screenshots = {}
        if save_dir:
            screenshots["desktop"] = await self._screenshot(page, save_dir, index, "desktop")
            if multi_viewport:
                screenshots["tablet"] = await self._screenshot_tablet(page, save_dir, index)
                screenshots["mobile"] = await self._screenshot_mobile(page, save_dir, index)
            # Focus crop if modal/dialog present
            if has_modal:
                focus_crop = await self._screenshot_focus(page, save_dir, index)
                if focus_crop:
                    screenshots["focus"] = focus_crop
        else:
            screenshots["desktop"] = await self._screenshot(page, save_dir, index, "desktop")
        
        # Get screenshot bytes for vision analysis
        screenshot_bytes = await page.screenshot(full_page=False)
        
        # Vision-based state significance analysis
        vision_significance = None
        if self.vision_analyzer:
            current_state = {
                "url": url,
                "has_modal": has_modal,
                "has_toast": has_toast,
                "form_validity": form_validity,
            }
            try:
                vision_significance = await self.vision_analyzer.analyze_significance(
                    screenshot_bytes,
                    self._task_context or "",
                    current_state,
                    self._previous_state,
                )
            except Exception as e:
                from parallax.core.logging import get_logger
                log = get_logger("detectors")
                log.warning("vision_significance_failed", error=str(e))
        
        metadata = {
            "roles": [r.__dict__ for r in roles[:200]],
            "has_toast": has_toast,
            "form_validity": form_validity,
            "has_loader": has_loader,
            "role_diff": role_diff,
        }

        significance = self._determine_significance(
            url=url,
            has_modal=has_modal,
            has_toast=has_toast,
            form_validity=form_validity,
            role_diff=role_diff,
            has_loader=has_loader,
        )
        metadata.update(significance)

        # Add vision analysis to metadata
        if vision_significance:
            metadata["vision_analysis"] = vision_significance
            metadata["significance"] = vision_significance.get(
                "significance", metadata.get("significance", "optional")
            )
            metadata["significance_confidence"] = vision_significance.get(
                "confidence", metadata.get("significance_confidence", 0.5)
            )
            metadata["significance_reasoning"] = vision_significance.get(
                "reasoning", metadata.get("significance_reasoning", "")
            )

        state = UIState(
            id=f"state_{signature[:8]}",
            url=url,
            description=description,
            has_modal=has_modal,
            action=action_desc,
            screenshots=screenshots,
            metadata=metadata,
            state_signature=signature,
        )
        
        # Store as previous state for next analysis
        self._previous_state = {
            "url": url,
            "has_modal": has_modal,
            "has_toast": has_toast,
            "form_validity": form_validity,
        }
        
        return state

    async def _screenshot(self, page, save_dir: Optional[Path], index: int, viewport: str = "desktop") -> str:
        filename = f"{index:02d}_full.png"
        if save_dir is None:
            await page.screenshot(path=filename, full_page=True)
            return filename
        save_dir.mkdir(parents=True, exist_ok=True)
        out = save_dir / filename
        await page.screenshot(path=str(out), full_page=True)
        await self._redact_viewport(page, out)
        return filename

    async def _screenshot_tablet(self, page, save_dir: Path, index: int) -> str:
        # Save original viewport so we can restore after resizing
        original_size = page.viewport_size
        capture_cfg = self.config.get("capture", {})
        desktop_viewport = capture_cfg.get("desktop_viewport", {"width": 1366, "height": 832})
        viewport = capture_cfg.get("tablet_viewport", {"width": 834, "height": 1112})
        await page.set_viewport_size(viewport)
        filename = f"{index:02d}_tablet.png"
        out = save_dir / filename
        await page.screenshot(path=str(out), full_page=True)
        
        await self._redact_viewport(page, out)
        
        # Restore to original viewport if available, otherwise fall back to desktop default
        await page.set_viewport_size(original_size or desktop_viewport)
        return filename

    async def _screenshot_mobile(self, page, save_dir: Path, index: int) -> str:
        # Save original viewport so we can restore after resizing
        original_size = page.viewport_size
        capture_cfg = self.config.get("capture", {})
        desktop_viewport = capture_cfg.get("desktop_viewport", {"width": 1366, "height": 832})
        mobile_viewport = capture_cfg.get("mobile_viewport", {"width": 390, "height": 844})
        await page.set_viewport_size(mobile_viewport)
        filename = f"{index:02d}_mobile.png"
        out = save_dir / filename
        await page.screenshot(path=str(out), full_page=True)
        
        await self._redact_viewport(page, out)
        
        # Restore to original viewport if available, otherwise fall back to desktop default
        await page.set_viewport_size(original_size or desktop_viewport)
        return filename

    async def _screenshot_focus(self, page, save_dir: Path, index: int) -> Optional[str]:
        script = """
        () => {
          const dialog = document.querySelector('[role="dialog"]');
          if (!dialog) return null;
          const rect = dialog.getBoundingClientRect();
          return {
            x: Math.max(0, rect.x - 16),
            y: Math.max(0, rect.y - 16),
            width: rect.width + 32,
            height: rect.height + 32
          };
        }
        """
        bounds = await page.evaluate(script)
        if not bounds:
            return None
        filename = f"{index:02d}_focus.png"
        out = save_dir / filename
        await page.screenshot(
            path=str(out),
            clip=bounds,
        )
        
        capture_cfg = self.config.get("capture", {})
        redact_screenshot(out, [bounds], capture_cfg)
        
        return filename

    async def _detect_toast(self, page) -> bool:
        script = """
        () => {
          const status = document.querySelector('[role="status"], [role="alert"]');
          const toast = document.querySelector('.toast, [class*="toast"], [class*="Toast"]');
          return !!(status || toast);
        }
        """
        return await page.evaluate(script)

    async def _check_form_validity(self, page) -> Optional[bool]:
        script = """
        () => {
          const forms = document.querySelectorAll('form');
          if (forms.length === 0) return null;
          for (const form of forms) {
            if (form.querySelector(':invalid')) return false;
          }
          return true;
        }
        """
        result = await page.evaluate(script)
        if result is not None and self._previous_form_validity is not None:
            if result != self._previous_form_validity:
                self._previous_form_validity = result
                return result  # Validity changed
        if result is not None:
            self._previous_form_validity = result
        return result

    async def _detect_loader(self, page) -> bool:
        script = """
        () => {
          const busy = document.querySelector('[aria-busy="true"]');
          const progressbar = document.querySelector('[role="progressbar"]');
          const spinner = document.querySelector('[class*="spinner"], [class*="loading"], [class*="loader"]');
          return !!(busy || progressbar || spinner);
        }
        """
        return await page.evaluate(script)

    def _compute_role_diff(self, roles: List[RoleNode]) -> Optional[float]:
        if self._previous_roles is None:
            self._previous_roles = roles
            return None
        threshold = self.config.get("role_diff_threshold", 0.2)
        similarity = jaccard_similarity(self._previous_roles, roles)
        diff = 1.0 - similarity
        self._previous_roles = roles
        if diff > threshold:
            return diff
        return None

    async def _extract_role_tree(self, page) -> List[RoleNode]:
        script = """
        () => {
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
          const nodes = [];
          while (walker.nextNode()) {
            const el = walker.currentNode;
            const role = el.getAttribute('role');
            if (!role) continue;
            const name = el.getAttribute('aria-label') || el.textContent?.trim()?.slice(0,80) || null;
            nodes.push({ role, name });
            if (nodes.length >= 200) break;
          }
          return nodes;
        }
        """
        data = await page.evaluate(script)
        return [RoleNode(role=n.get("role"), name=n.get("name")) for n in data]

    def _hash_signature(self, url: str, roles: List[RoleNode]) -> str:
        payload = json.dumps({
            "url": url,
            "roles": [(r.role, r.name) for r in roles[:50]],
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _describe(
        self,
        url: str,
        roles: List[RoleNode],
        has_toast: bool,
        form_validity: Optional[bool],
        has_loader: bool,
        role_diff: Optional[float],
    ) -> str:
        parsed = urlparse(url)
        path = parsed.path or "/"
        page_label = path.strip("/") or "home"
        parts = [f"{page_label.capitalize()} page"]

        dialogs = [r for r in roles if r.role == "dialog"]
        if dialogs:
            parts.append("Dialog open")
        if has_toast:
            parts.append("Toast visible")
        if form_validity is False:
            parts.append("Form invalid")
        elif form_validity is True:
            parts.append("Form valid")
        if has_loader:
            parts.append("Loading")
        if role_diff is not None:
            parts.append(f"Structure changed ({role_diff:.2f})")

        return " | ".join(parts)

    async def _redact_viewport(self, page, image_path: Path) -> None:
        capture_cfg = self.config.get("capture", {})
        redact_cfg = capture_cfg.get("redact", {})
        selectors = redact_cfg.get("selectors", [])
        if not selectors or not redact_cfg.get("enabled", False):
            return
        try:
            regions = await self._get_redaction_regions(page, selectors)
        except Exception:
            return
        if regions:
            redact_screenshot(image_path, regions, capture_cfg)

    async def _get_redaction_regions(self, page, selectors: List[str]) -> List[Dict[str, float]]:
        script = """
        (selectors) => {
          const out = [];
          selectors.forEach((sel) => {
            try {
              document.querySelectorAll(sel).forEach((el) => {
                const rect = el.getBoundingClientRect();
                if (rect.width && rect.height) {
                  out.push({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });
                }
              });
            } catch (err) {}
          });
          return out;
        }
        """
        result = await page.evaluate(script, selectors)
        return result or []

    def _determine_significance(
        self,
        url: str,
        has_modal: bool,
        has_toast: bool,
        form_validity: Optional[bool],
        role_diff: Optional[float],
        has_loader: bool,
    ) -> Dict[str, Any]:
        significance = "optional"
        confidence = 0.5
        reasoning: List[str] = []
        previous_url = (self._previous_state or {}).get("url")
        if url and url != previous_url:
            path = urlparse(url).path or "/"
            label = path.strip("/") or "home"
            significance = "supporting"
            confidence = 0.65
            reasoning.append(f"Navigated to {label}")

        if has_modal or has_toast:
            significance = "critical"
            confidence = 0.85
            if has_modal:
                reasoning.append("Modal dialog visible")
            if has_toast:
                reasoning.append("Toast/alert detected")
        elif form_validity is True and not has_loader:
            significance = "supporting"
            confidence = 0.7
            reasoning.append("Form validated successfully")
        elif has_loader:
            significance = "supporting"
            confidence = 0.6
            reasoning.append("Loading indicator detected")

        if role_diff is not None and role_diff > 0.2 and significance != "critical":
            significance = "supporting"
            confidence = max(confidence, 0.65)
            reasoning.append("Significant role-tree change")

        if not reasoning:
            reasoning.append("Stable navigation state")

        return {
            "significance": significance,
            "significance_confidence": confidence,
            "significance_reasoning": "; ".join(reasoning),
        }


