const knownErrorMessages: Record<string, string> = {
  "Invalid credentials": "用户名或密码不正确",
  "bad credentials": "用户名或密码不正确",
  "Request failed": "",
};

export function friendlyErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message.trim()) {
    return fallback;
  }

  const known = knownErrorMessages[error.message.trim()];
  if (known !== undefined) {
    return known || fallback;
  }

  return hasChinese(error.message) ? error.message : fallback;
}

function hasChinese(value: string): boolean {
  return /[\u4e00-\u9fff]/.test(value);
}
