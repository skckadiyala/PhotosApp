import { useMutation } from '@tanstack/react-query';
import { login, register } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

export function useLogin() {
  const setTokens = useAuthStore((s) => s.setTokens);

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (data) => {
      setTokens(data.access_token, data.refresh_token);
    },
  });
}

export function useRegister() {
  const setTokens = useAuthStore((s) => s.setTokens);

  return useMutation({
    mutationFn: ({
      username,
      email,
      password,
    }: {
      username: string;
      email: string;
      password: string;
    }) => register(username, email, password),
    onSuccess: (data) => {
      setTokens(data.access_token, data.refresh_token);
    },
  });
}
