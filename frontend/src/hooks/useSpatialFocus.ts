import { useEffect } from 'react';

const directions = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'] as const;

/** Geometry-based focus movement for directional TV remotes and desktop preview. */
export function useSpatialFocus(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!directions.includes(event.key as typeof directions[number])) return;
      const modal = document.querySelector<HTMLElement>('[role="dialog"][aria-modal="true"]');
      const scope: ParentNode = modal || document;
      const current = document.activeElement as HTMLElement | null;
      if (modal && current && !modal.contains(current)) {
        scope.querySelector<HTMLElement>('[data-focusable="true"]')?.focus({ preventScroll: true });
        event.preventDefault();
        return;
      }
      if (!current || !current.matches('[data-focusable="true"]')) return;
      if (current.matches('input, textarea, select, [contenteditable="true"]')) return;
      const candidates = [...scope.querySelectorAll<HTMLElement>('[data-focusable="true"]')]
        .filter((node) => node !== current && !node.hasAttribute('disabled') && node.offsetParent !== null);
      const a = current.getBoundingClientRect();
      const acx = a.left + a.width / 2; const acy = a.top + a.height / 2;
      const direction = event.key;
      const scored = candidates.map((node) => {
        const b = node.getBoundingClientRect();
        const x = b.left + b.width / 2; const y = b.top + b.height / 2;
        const dx = x - acx; const dy = y - acy;
        const inDirection = direction === 'ArrowRight' ? dx > 3 : direction === 'ArrowLeft' ? dx < -3 : direction === 'ArrowDown' ? dy > 3 : dy < -3;
        if (!inDirection) return { node, score: Number.POSITIVE_INFINITY };
        const primary = direction === 'ArrowRight' || direction === 'ArrowLeft' ? Math.abs(dx) : Math.abs(dy);
        const secondary = direction === 'ArrowRight' || direction === 'ArrowLeft' ? Math.abs(dy) : Math.abs(dx);
        return { node, score: primary + secondary * 2.5 };
      }).sort((left, right) => left.score - right.score);
      event.preventDefault();
      if (scored[0] && Number.isFinite(scored[0].score)) {
        scored[0].node.focus({ preventScroll: true });
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [enabled]);
}
