import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import LibraryPage from './pages/LibraryPage';
import PhotoDetailPage from './pages/PhotoDetailPage';
import AlbumsPage from './pages/AlbumsPage';
import AlbumDetailPage from './pages/AlbumDetailPage';
import PeoplePage from './pages/PeoplePage';
import PersonDetailPage from './pages/PersonDetailPage';
import MapPage from './pages/MapPage';
import SearchPage from './pages/SearchPage';
import FavoritesPage from './pages/FavoritesPage';
import FaceConfirmPage from './pages/FaceConfirmPage';
import VideosPage from './pages/VideosPage';
import MonthDetailPage from './pages/MonthDetailPage';
import EventDetailPage from './pages/EventDetailPage';
import VideoMonthDetailPage from './pages/VideoMonthDetailPage';
import VideoEventDetailPage from './pages/VideoEventDetailPage';

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
                <Route path="/" element={<Navigate to="/library" replace />} />
                <Route path="/library" element={<LibraryPage />} />
                {/* Legacy redirect: old /timeline bookmarks go to library */}
                <Route path="/timeline" element={<Navigate to="/library" replace />} />
                <Route path="/videos" element={<VideosPage />} />
                <Route path="/videos/month/:year/:month" element={<VideoMonthDetailPage />} />
                <Route path="/videos/event/:clusterId" element={<VideoEventDetailPage />} />
                <Route path="/library/month/:year/:month" element={<MonthDetailPage />} />
                <Route path="/library/event/:clusterId" element={<EventDetailPage />} />
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
