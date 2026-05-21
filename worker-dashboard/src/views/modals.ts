/** Modal dialogs — Mustache template rendering */

import detailModalTemplate from "../templates/partials/detail-modal.mustache";
import registerModalTemplate from "../templates/partials/register-modal.mustache";
import registerKiroModalTemplate from "../templates/partials/register-kiro-modal.mustache";

export function renderDetailModal(): string {
  return detailModalTemplate;
}

export function renderRegisterModal(): string {
  return registerModalTemplate;
}

export function renderRegisterKiroModal(): string {
  return registerKiroModalTemplate;
}
