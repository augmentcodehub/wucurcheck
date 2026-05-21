/** Route handler and routing types. */

export type RouteHandler = (request: Request, env: Env) => Promise<Response>;

export interface Route {
  method: "GET" | "POST";
  path: string;
  handler: RouteHandler;
}
