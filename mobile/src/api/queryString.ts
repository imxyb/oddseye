export type QueryValue = string | number | boolean | null | undefined;

export function toQueryString(params: object): string {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    const queryValue = value as QueryValue;

    if (queryValue !== undefined && queryValue !== null && queryValue !== "") {
      search.set(key, String(queryValue));
    }
  });

  const query = search.toString();
  return query ? `?${query}` : "";
}
