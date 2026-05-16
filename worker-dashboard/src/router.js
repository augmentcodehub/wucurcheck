import { pageAccounts, apiAccounts } from "./pages/accounts.js";
import { apiTrigger } from "./pages/actions.js";

const routes = [
  ["GET", "/", pageAccounts],
  ["GET", "/api/accounts", apiAccounts],
  ["POST", "/api/trigger", apiTrigger],
];

export async function router(path, method, request, env) {
  const route = routes.find(([m, p]) => m === method && p === path);
  if (route) return route[2](request, env);
  return new Response("Not Found", { status: 404 });
}
