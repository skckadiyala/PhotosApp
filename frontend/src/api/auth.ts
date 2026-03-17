import api from './client';

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password });
  return data;
}

export async function register(username: string, email: string, password: string) {
  const { data } = await api.post('/auth/register', { username, email, password });
  return data;
}

export async function getMe() {
  const { data } = await api.get('/auth/me');
  return data;
}
