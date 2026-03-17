import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import PhotosPage from './pages/PhotosPage';
import PhotoDetailPage from './pages/PhotoDetailPage';
import AlbumsPage from './pages/AlbumsPage';
import AlbumDetailPage from './pages/AlbumDetailPage';
import PeoplePage from './pages/PeoplePage';
import PersonDetailPage from './pages/PersonDetailPage';
import MapPage from './pages/MapPage';
import SearchPage from './pages/SearchPage';
import FavoritesPage from './pages/FavoritesPage';
import FaceConfirmPage from './pages/FaceConfirmPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppShell>
              <Routes>
                <Route path="/" element={<Navigate to="/timeline" replace />} />
                <Route path="/timeline" element={<PhotosPage />} />
                <Route path="/photo/:id" element={<PhotoDetailPage />} />
                <Route path="/albums" element={<AlbumsPage />} />
                <Route path="/albums/:id" element={<AlbumDetailPage />} />
                <Route path="/people" element={<PeoplePage />} />
                <Route path="/people/confirm" element={<FaceConfirmPage />} />
                <Route path="/people/:id" element={<PersonDetailPage />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/favorites" element={<FavoritesPage />} />
              </Routes>
            </AppShell>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
