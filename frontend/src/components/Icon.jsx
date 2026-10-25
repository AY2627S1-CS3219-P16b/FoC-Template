import React from "react";

const paths = {
  bag: <><path d="M6 7h12l2 14H4L6 7Z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></>,
  pin: <><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  arrow: <path d="M4 12h16M14 6l6 6-6 6" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  coins: <><ellipse cx="10" cy="6" rx="7" ry="3" /><path d="M3 6v5c0 1.7 3.1 3 7 3m0-5c3.9 0 7-1.3 7-3v4M3 11v5c0 1.7 3.1 3 7 3" /><path d="M14 14c0-1.1 1.6-2 3.5-2s3.5.9 3.5 2v5c0 1.1-1.6 2-3.5 2s-3.5-.9-3.5-2v-5Z" /><path d="M14 14c0 1.1 1.6 2 3.5 2s3.5-.9 3.5-2" /></>,
  store: <><path d="m4 3-2 6a3 3 0 0 0 5 2 3 3 0 0 0 5 0 3 3 0 0 0 5 0 3 3 0 0 0 5-2l-2-6H4ZM4 12v9h16v-9M9 21v-7h6v7" /></>,
  list: <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 3h6v4H9zM9 12h6M9 16h6" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  logout: <path d="M9 4H4v16h5M10 12h11M17 8l4 4-4 4" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
};

export default function Icon({ name, className = "" }) {
  return <svg className={`ui-icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{paths[name] || paths.bag}</svg>;
}
