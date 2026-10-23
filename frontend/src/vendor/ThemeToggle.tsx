// Copyright (c) 2026 Swami Malode. Adapted from Rare UI. See RareUI-LICENSE.txt.
"use client";



const ContrastIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
    <path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" />
    <path d="M12 3l0 18" />
    <path d="M12 9l4.65 -4.65" />
    <path d="M12 14.3l7.37 -7.37" />
    <path d="M12 19.6l8.85 -8.85" />
  </svg>
);

export default function ThemeToggle({dark,onToggle}:{dark:boolean;onToggle:()=>void}) {
  return <button type="button" className="theme-toggle" role="switch" aria-checked={dark} aria-label="Dark mode" onClick={onToggle} title={dark?'Switch to light mode':'Switch to dark mode'}>
    <span className="theme-track" aria-hidden="true"><span className="theme-thumb"><ContrastIcon/></span></span>
  </button>;
}
