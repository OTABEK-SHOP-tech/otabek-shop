import { useState, useEffect, useRef } from 'react';

export interface UseScrollRevealOptions {
  /** Threshold ratio of element visibility required to trigger reveal (0 to 1). Default: 0.08 */
  threshold?: number;
  /** Root margin offset string for intersection bounding box. Default: '0px 0px -20px 0px' */
  rootMargin?: string;
  /** Whether animation is disabled (e.g. reduced-motion). When true, reveals immediately. */
  disabled?: boolean;
  /** Whether animation triggers only once or on every scroll in/out. Default: false (continuous on scroll) */
  once?: boolean;
}

export interface UseScrollRevealReturn {
  ref: React.RefObject<HTMLDivElement>;
  isVisible: boolean;
  isSettled: boolean;
  handleTransitionEnd: (e: React.TransitionEvent<HTMLDivElement>) => void;
}

/**
 * High-performance, 60fps scroll reveal hook optimized for Telegram Mini App WebViews.
 * - Continuous re-animation on scroll (once: false) so cards smoothly re-reveal on every scroll
 * - Immediate cleanup/unmount on component unmount to prevent memory leaks
 * - Settled state management with safety timer fallback to release GPU layers
 * - Safe fallbacks for environments without IntersectionObserver or with reduced-motion
 */
export function useScrollReveal(options: UseScrollRevealOptions = {}): UseScrollRevealReturn {
  const { threshold = 0.08, rootMargin = '0px 0px -20px 0px', disabled = false, once = false } = options;
  const [isVisible, setIsVisible] = useState(disabled);
  const [isSettled, setIsSettled] = useState(disabled);
  const elementRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // If once is true and already revealed and settled, skip observer setup
    if (once && isVisible && isSettled) return;

    // If motion is disabled by user setting, reveal immediately with no delay
    if (disabled) {
      setIsVisible(true);
      setIsSettled(true);
      return;
    }

    // SSR or headless environment guard
    if (typeof window === 'undefined') {
      setIsVisible(true);
      setIsSettled(true);
      return;
    }

    // OS-level prefers-reduced-motion accessibility guard
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setIsVisible(true);
      setIsSettled(true);
      return;
    }

    // Fallback if browser/WebView doesn't support IntersectionObserver
    if (!('IntersectionObserver' in window)) {
      setIsVisible(true);
      setIsSettled(true);
      return;
    }

    const node = elementRef.current;
    if (!node) return;

    let observer: IntersectionObserver | null = new IntersectionObserver(
      (entries, obs) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setIsVisible(true);
            if (once) {
              obs.unobserve(entry.target);
              obs.disconnect();
              observer = null;
              break;
            }
          } else {
            if (!once) {
              setIsVisible(false);
              setIsSettled(false);
            }
          }
        }
      },
      {
        root: null, // viewport
        rootMargin,
        threshold,
      }
    );

    observer.observe(node);

    // Guaranteed unmount cleanup to prevent memory leaks in mobile WebViews
    return () => {
      if (observer) {
        if (node) {
          observer.unobserve(node);
        }
        observer.disconnect();
        observer = null;
      }
    };
  }, [disabled, threshold, rootMargin, once]);

  // Safety fallback: once visible, ensure isSettled becomes true even if transitionend was dropped
  useEffect(() => {
    if (isVisible && !isSettled) {
      const timer = window.setTimeout(() => {
        setIsSettled(true);
      }, 700);
      return () => window.clearTimeout(timer);
    }
  }, [isVisible, isSettled]);

  const handleTransitionEnd = (e: React.TransitionEvent<HTMLDivElement>) => {
    // Only handle transitions fired on this container, not child elements
    if (e.target === elementRef.current && (e.propertyName === 'transform' || e.propertyName === 'opacity')) {
      setIsSettled(true);
    }
  };

  return {
    ref: elementRef,
    isVisible,
    isSettled,
    handleTransitionEnd,
  };
}
