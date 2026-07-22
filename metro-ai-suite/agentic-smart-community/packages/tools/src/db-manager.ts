export interface DbQueryParams {
  query: string;
  params?: unknown[];
}

export async function dbManager(params: DbQueryParams): Promise<unknown[]> {
  // TODO: implement
  return [];
}
