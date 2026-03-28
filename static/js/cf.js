import { createRuntime } from "./cf/shared.js";
import { createShell } from "./cf/shell.js";
import { initDashboard } from "./cf/pages/dashboard.js";
import { initDiagnostics } from "./cf/pages/diagnostics.js";
import { initChannels } from "./cf/pages/channels.js";
import { initSettings } from "./cf/pages/settings.js";
import { initStudio } from "./cf/studio/actions.js";

const page = document.body?.dataset.page || "";
const ctx = createRuntime(page);
const shell = createShell(ctx);

function dispatchPage() {
  if (page === "dashboard") return initDashboard(ctx);
  if (page === "channels") return initChannels(ctx);
  if (page === "settings") return initSettings(ctx, shell);
  if (page === "diagnostics") return initDiagnostics(ctx);
  if (page === "studio") return initStudio(ctx);
  return null;
}

ctx.rehydrateCurrentPage = () => {
  shell.hydrateShell();
  return dispatchPage();
};

document.addEventListener("DOMContentLoaded", () => {
  ctx.toastHost();
  shell.initShell();
  dispatchPage();
});
