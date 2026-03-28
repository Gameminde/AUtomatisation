import { ReactNode } from "react";

export function EmptyState({
  title,
  copy,
  action,
}: {
  title: string;
  copy: string;
  action?: ReactNode;
}) {
  return (
    <div className="cf-empty-state">
      <div className="cf-empty-title">{title}</div>
      <div className="cf-empty-copy">{copy}</div>
      {action}
    </div>
  );
}

export function ErrorState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="cf-error-state">
      <div className="cf-error-title">{title}</div>
      <div className="cf-error-copy">{copy}</div>
    </div>
  );
}
