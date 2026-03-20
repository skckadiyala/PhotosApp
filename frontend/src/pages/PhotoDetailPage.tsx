import { useParams, useNavigate, useLocation, NavLink } from 'react-router-dom';
import { useEffect, useCallback, useState, useRef, useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import toast from 'react-hot-toast';
import { usePhoto, usePhotos } from '../hooks/usePhotos';
import { useFacesForPhoto, usePeople } from '../hooks/useFaces';
import { useAlbums } from '../hooks/useAlbums';
import { getOriginalUrl, getThumbnailUrl, scanPhotoFaces, addManualFace, toggleFavorite } from '../api/photos';
import { addPhotosToAlbum } from '../api/albums';
import { assignFace, deleteFace, getFaceThumbnailUrl } from '../api/faces';
import AuthImage, { prefetchAuthImage, isImageCached } from '../components/common/AuthImage';
import { useAuthStore } from '../stores/authStore';
import Spinner from '../components/common/Spinner';
import type { Face, Person } from '../types/face';
import type { Album } from '../types/album';

const ZOOM_MIN = 1;
const ZOOM_MAX = 4;
const ZOOM_STEP = 0.5;

export default function PhotoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { data: photo, isLoading } = usePhoto(id);
  const { data: photoFaces = [] } = useFacesForPhoto(id);
  const { data: albumsData } = useAlbums();
  const { data: peopleData } = usePeople();
  const { data: photosData } = usePhotos();
  const [showInfo, setShowInfo] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [showAlbumPicker, setShowAlbumPicker] = useState(false);

  // Context passed from the originating page
  const contextPhotoIds: string[] | undefined = (location.state as { photoIds?: string[]; returnTo?: string; direction?: string } | null)?.photoIds;
  const returnTo: string | undefined = (location.state as { photoIds?: string[]; returnTo?: string; direction?: string } | null)?.returnTo;
  const navDirection: string | undefined = (location.state as { photoIds?: string[]; returnTo?: string; direction?: string } | null)?.direction;
  const [assigningFaceId, setAssigningFaceId] = useState<string | null>(null);
  const [newPersonName, setNewPersonName] = useState('');
  const [scanningFaces, setScanningFaces] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);
  const accessToken = useAuthStore((s: { accessToken: string | null }) => s.accessToken);

  // Reset loaded state when photo changes — skip fade-in animation if already cached
  useEffect(() => {
    if (id && isImageCached(`/api/v1/photos/${id}/original`)) {
      setImgLoaded(true);
    } else {
      setImgLoaded(false);
    }
  }, [id]);

  // ── Manual face draw mode ──────────────────────────────────
  const [drawMode, setDrawMode] = useState(false);
  const [drawRect, setDrawRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [submittingFace, setSubmittingFace] = useState(false);
  const drawStart = useRef<{ x: number; y: number } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Enter draw mode: reset zoom/pan so coordinate mapping is trivial
  const enterDrawMode = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setDrawRect(null);
    setDrawMode(true);
  };
  const exitDrawMode = () => {
    setDrawMode(false);
    setDrawRect(null);
    drawStart.current = null;
  };

  // Redraw the selection rectangle on the canvas whenever drawRect changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!drawRect) return;
    const { x, y, w, h } = drawRect;
    // Dim overlay
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    // Cut out the selection
    ctx.clearRect(x, y, w, h);
    // Selection border
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    // Corner handles
    const hs = 8;
    ctx.fillStyle = '#3b82f6';
    [[x, y], [x + w, y], [x, y + h], [x + w, y + h]].forEach(([cx, cy]) => {
      ctx.fillRect(cx - hs / 2, cy - hs / 2, hs, hs);
    });
  }, [drawRect]);

  // Resize canvas to match container
  useEffect(() => {
    if (!drawMode) return;
    const container = imageContainerRef.current;
    if (!container) return;
    const resize = () => {
      if (canvasRef.current) {
        canvasRef.current.width = container.clientWidth;
        canvasRef.current.height = container.clientHeight;
      }
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);
    return () => ro.disconnect();
  }, [drawMode]);

  const getCanvasPos = (e: React.MouseEvent): { x: number; y: number } => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    const pos = getCanvasPos(e);
    drawStart.current = pos;
    setDrawRect({ x: pos.x, y: pos.y, w: 0, h: 0 });
  };
  const handleCanvasMouseMove = (e: React.MouseEvent) => {
    if (!drawStart.current) return;
    const pos = getCanvasPos(e);
    setDrawRect({
      x: Math.min(pos.x, drawStart.current.x),
      y: Math.min(pos.y, drawStart.current.y),
      w: Math.abs(pos.x - drawStart.current.x),
      h: Math.abs(pos.y - drawStart.current.y),
    });
  };
  const handleCanvasMouseUp = () => { drawStart.current = null; };

  // Map canvas px → original image px
  const canvasRectToImageCoords = (rect: { x: number; y: number; w: number; h: number }) => {
    const img = imgRef.current;
    if (!img || !photo?.width || !photo?.height) return null;
    const imgRect = img.getBoundingClientRect();
    const canvas = canvasRef.current!;
    const canvasRect = canvas.getBoundingClientRect();
    // img position relative to canvas
    const imgLeft = imgRect.left - canvasRect.left;
    const imgTop  = imgRect.top  - canvasRect.top;
    const scaleX = photo.width  / imgRect.width;
    const scaleY = photo.height / imgRect.height;
    return {
      top:    Math.round((rect.y - imgTop)          * scaleY),
      bottom: Math.round((rect.y + rect.h - imgTop) * scaleY),
      left:   Math.round((rect.x - imgLeft)          * scaleX),
      right:  Math.round((rect.x + rect.w - imgLeft) * scaleX),
    };
  };

  const handleConfirmFace = async () => {
    if (!drawRect || !id) return;
    const coords = canvasRectToImageCoords(drawRect);
    if (!coords) return;
    if (coords.bottom - coords.top < 20 || coords.right - coords.left < 20) {
      toast.error('Selection too small — please draw a larger area around the face');
      return;
    }
    setSubmittingFace(true);
    try {
      await addManualFace(id, coords);
      toast.success('Face region submitted — results will appear in a moment');
      exitDrawMode();
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['faces', 'photo', id] });
        queryClient.invalidateQueries({ queryKey: ['people'] });
      }, 5000);
    } catch {
      toast.error('Failed to submit face region');
    } finally {
      setSubmittingFace(false);
    }
  };

  const handleScanFaces = async () => {
    if (!id || scanningFaces) return;
    const hasNamedFaces = photoFaces.some((f: Face) => f.person_id);
    if (hasNamedFaces) {
      const ok = window.confirm(
        'Rescanning will re-detect faces on this photo. Named faces at the same position will keep their person assignments, but any faces the detector no longer finds will be removed. Continue?'
      );
      if (!ok) return;
    }
    setScanningFaces(true);
    try {
      await scanPhotoFaces(id);
      toast.success('Face scan started — results will appear in a moment');
      // Invalidate faces/people after a short delay to pick up new detections
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['faces', 'photo', id] });
        queryClient.invalidateQueries({ queryKey: ['people'] });
        queryClient.invalidateQueries({ queryKey: ['photo', id] });
      }, 5000);
    } catch {
      toast.error('Failed to start face scan');
    } finally {
      setScanningFaces(false);
    }
  };

  // ── Navigation ─────────────────────────────────────────────
  // allPhotos from the infinite query (fallback when no context IDs are provided)
  const allPhotosFlat = useMemo(
    () => photosData?.pages.flatMap((p) => p.items) ?? [],
    [photosData],
  );

  // When opened from a specific context (album, person, favorites, search),
  // use only those ordered IDs; otherwise fall back to the full timeline.
  const navPhotoIds: string[] = useMemo(
    () => contextPhotoIds ?? allPhotosFlat.map((p) => p.id),
    [contextPhotoIds, allPhotosFlat],
  );

  const currentIndex = navPhotoIds.indexOf(id ?? '');
  const prevId = currentIndex > 0 ? navPhotoIds[currentIndex - 1] : null;
  const nextId = currentIndex !== -1 && currentIndex < navPhotoIds.length - 1
    ? navPhotoIds[currentIndex + 1]
    : null;

  // Preload adjacent photos into blob cache so navigation is instant
  useEffect(() => {
    if (!accessToken) return;
    if (prevId) {
      prefetchAuthImage(getThumbnailUrl(prevId, 'sm'), accessToken);
      prefetchAuthImage(getThumbnailUrl(prevId, 'lg'), accessToken);
      prefetchAuthImage(getOriginalUrl(prevId), accessToken);
    }
    if (nextId) {
      prefetchAuthImage(getThumbnailUrl(nextId, 'sm'), accessToken);
      prefetchAuthImage(getThumbnailUrl(nextId, 'lg'), accessToken);
      prefetchAuthImage(getOriginalUrl(nextId), accessToken);
    }
  }, [prevId, nextId, accessToken]);

  const prevNavState = useMemo(
    () => ({ photoIds: contextPhotoIds, returnTo, direction: 'prev' }),
    [contextPhotoIds, returnTo],
  );
  const nextNavState = useMemo(
    () => ({ photoIds: contextPhotoIds, returnTo, direction: 'next' }),
    [contextPhotoIds, returnTo],
  );

  // ── Zoom + pan state ───────────────────────────────────────
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const panAtDrag = useRef({ x: 0, y: 0 });
  const imageContainerRef = useRef<HTMLDivElement>(null);
  // Ref for the outermost viewer div — used for the native wheel listener.
  const viewerRef = useRef<HTMLDivElement>(null);

  // Reset zoom/pan whenever the photo changes
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [id]);

  const clampZoom = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));

  const handleZoomIn = () => setZoom((z) => { const nz = clampZoom(z + ZOOM_STEP); if (nz === 1) setPan({ x: 0, y: 0 }); return nz; });
  const handleZoomOut = () => setZoom((z) => { const nz = clampZoom(z - ZOOM_STEP); if (nz === 1) setPan({ x: 0, y: 0 }); return nz; });
  const handleZoomReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // Native non-passive wheel listener so e.preventDefault() is guaranteed to
  // work and zoom fires regardless of where the cursor is in the viewer
  // (including over the prev/next nav arrows after clicking them).
  useEffect(() => {
    const container = viewerRef.current;
    if (!container) return;
    const onWheel = (e: WheelEvent) => {
      // Let the info sidebar scroll naturally
      if ((e.target as Element).closest?.('aside')) return;
      if (drawMode) return;
      e.preventDefault();
      setZoom((z) => {
        const nz = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z - Math.sign(e.deltaY) * ZOOM_STEP));
        if (nz === 1) setPan({ x: 0, y: 0 });
        return nz;
      });
    };
    container.addEventListener('wheel', onWheel, { passive: false });
    return () => container.removeEventListener('wheel', onWheel);
  }, [drawMode]);

  // Mouse pan
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom === 1) return;
    isDragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY };
    panAtDrag.current = pan;
    e.preventDefault();
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    setPan({
      x: panAtDrag.current.x + (e.clientX - dragStart.current.x),
      y: panAtDrag.current.y + (e.clientY - dragStart.current.y),
    });
  };
  const stopDrag = () => { isDragging.current = false; };

  // Touch pan
  const touchStart = useRef({ x: 0, y: 0 });
  const handleTouchStart = (e: React.TouchEvent) => {
    if (zoom === 1 || e.touches.length !== 1) return;
    touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    panAtDrag.current = pan;
  };
  const handleTouchMove = (e: React.TouchEvent) => {
    if (zoom === 1 || e.touches.length !== 1) return;
    setPan({
      x: panAtDrag.current.x + (e.touches[0].clientX - touchStart.current.x),
      y: panAtDrag.current.y + (e.touches[0].clientY - touchStart.current.y),
    });
  };

  const albums: Album[] = albumsData?.items ?? [];
  const people: Person[] = peopleData ?? [];

  const addToAlbumMutation = useMutation({
    mutationFn: (albumId: string) => addPhotosToAlbum(albumId, [id!]),
    onSuccess: (_data, albumId) => {
      const album = albums.find((a) => a.id === albumId);
      toast.success(`Added to "${album?.name ?? 'album'}"`);
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      queryClient.invalidateQueries({ queryKey: ['album', albumId] });
      setShowAlbumPicker(false);
    },
    onError: () => toast.error('Failed to add to album'),
  });

  const assignMutation = useMutation({
    mutationFn: (params: { faceId: string; person_id?: string; new_person_name?: string }) =>
      assignFace(params.faceId, { person_id: params.person_id, new_person_name: params.new_person_name }),
    onSuccess: (result) => {
      toast.success(result.person_name ? `Assigned to "${result.person_name}"` : 'Face assigned');
      queryClient.invalidateQueries({ queryKey: ['faces'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      setAssigningFaceId(null);
      setNewPersonName('');
    },
    onError: () => toast.error('Failed to assign face'),
  });

  const deleteFaceMutation = useMutation({
    mutationFn: (faceId: string) => deleteFace(faceId),
    onSuccess: () => {
      toast.success('Face removed');
      queryClient.invalidateQueries({ queryKey: ['faces'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
    onError: () => toast.error('Failed to delete face'),
  });

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't intercept arrow keys while typing in an input/textarea
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return;
      if (e.key === 'Escape') {
        if (drawMode) { exitDrawMode(); return; }
        if (returnTo) navigate(returnTo, { state: { scrollToId: id } });
        else navigate(-1 as never);
      }
      if (e.key === 'ArrowLeft' && prevId) navigate(`/photo/${prevId}`, { state: prevNavState });
      if (e.key === 'ArrowRight' && nextId) navigate(`/photo/${nextId}`, { state: nextNavState });
      if (e.key === '+' || e.key === '=') handleZoomIn();
      if (e.key === '-') handleZoomOut();
      if (e.key === '0') handleZoomReset();
    },
    [navigate, prevId, nextId, prevNavState, nextNavState],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Keep the full-screen black overlay during any loading state so the
  // underlying grid page never shows through.
  if (isLoading || !photo) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
        {isLoading && <Spinner />}
      </div>
    );
  }

  const navItems = [
    { to: '/timeline', label: 'Timeline', icon: '📷' },
    { to: '/albums', label: 'Albums', icon: '📁' },
    { to: '/people', label: 'People', icon: '👤' },
    { to: '/map', label: 'Map', icon: '🗺️' },
    { to: '/search', label: 'Search', icon: '🔍' },
    { to: '/favorites', label: 'Favorites', icon: '❤️' },
  ];

  return (
    <div ref={viewerRef} className="fixed inset-0 z-50 flex bg-black">
      {/* Top-left controls: hamburger + back */}
      <div className="absolute left-4 top-4 z-[60] flex items-center gap-2">
        <button
          onClick={() => setNavOpen((o) => !o)}
          aria-label="Toggle navigation"
          className="rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <button
          onClick={() => { if (returnTo) navigate(returnTo, { state: { scrollToId: id } }); else navigate(-1 as never); }}
          aria-label="Back"
          className="rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Favorite toggle */}
      <button
        onClick={async () => {
          if (!id) return;
          try {
            await toggleFavorite(id, !photo.is_favorite);
            queryClient.invalidateQueries({ queryKey: ['photo', id] });
            queryClient.invalidateQueries({ queryKey: ['photos'] });
          } catch {
            toast.error('Failed to update favorite');
          }
        }}
        aria-label={photo.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
        className="absolute right-16 top-4 z-[60] rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
      >
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill={photo.is_favorite ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
      </button>

      {/* Info toggle */}
      <button
        onClick={() => setShowInfo(!showInfo)}
        aria-label="Toggle info"
        className="absolute right-4 top-4 z-[60] rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {/* Left nav panel */}
      {navOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[65] bg-black/40"
            onClick={() => setNavOpen(false)}
          />
          {/* Panel */}
          <div
            className={`fixed left-0 top-0 z-[70] flex h-full flex-col bg-gray-950 shadow-2xl transition-all duration-200 ${
              navCollapsed ? 'w-16' : 'w-56'
            }`}
          >
            {/* Panel header */}
            <div className="flex h-14 items-center justify-between border-b border-gray-800 px-3">
              {!navCollapsed && (
                <span className="text-base font-semibold text-white">📸 PhotosApp</span>
              )}
              <button
                onClick={() => setNavCollapsed((c) => !c)}
                aria-label={navCollapsed ? 'Expand nav' : 'Collapse nav'}
                className="ml-auto rounded p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d={navCollapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'}
                  />
                </svg>
              </button>
            </div>

            {/* Nav items */}
            <nav className="flex-1 py-4">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setNavOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-900/60 text-primary-400 border-r-2 border-primary-500'
                        : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                    }`
                  }
                >
                  <span className="text-lg leading-none">{item.icon}</span>
                  {!navCollapsed && <span>{item.label}</span>}
                </NavLink>
              ))}
            </nav>

            {/* Back to close */}
            {!navCollapsed && (
              <div className="border-t border-gray-800 p-3">
                <button
                  onClick={() => { if (returnTo) navigate(returnTo, { state: { scrollToId: id } }); else navigate(-1 as never); }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Close photo
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* Prev arrow */}
      {prevId && (
        <button
          onClick={() => navigate(`/photo/${prevId}`, { state: prevNavState })}
          aria-label="Previous photo"
          className="absolute left-4 top-1/2 z-20 -translate-y-1/2 rounded-full bg-black/50 p-3 text-white opacity-0 transition-opacity hover:bg-black/80 focus:opacity-100 group-hover:opacity-100"
          style={{ opacity: undefined }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
          onFocus={(e) => (e.currentTarget.style.opacity = '1')}
          onBlur={(e) => (e.currentTarget.style.opacity = '0')}
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Next arrow */}
      {nextId && (
        <button
          onClick={() => navigate(`/photo/${nextId}`, { state: nextNavState })}
          aria-label="Next photo"
          className="absolute right-4 top-1/2 z-20 -translate-y-1/2 rounded-full bg-black/50 p-3 text-white opacity-0 transition-opacity hover:bg-black/80 focus:opacity-100"
          style={{ opacity: undefined }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
          onFocus={(e) => (e.currentTarget.style.opacity = '1')}
          onBlur={(e) => (e.currentTarget.style.opacity = '0')}
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Main image area */}
      <div
        ref={imageContainerRef}
        className="relative flex-1 flex items-center justify-center overflow-hidden"
        onMouseDown={drawMode ? undefined : handleMouseDown}
        onMouseMove={drawMode ? undefined : handleMouseMove}
        onMouseUp={drawMode ? undefined : stopDrag}
        onMouseLeave={drawMode ? undefined : stopDrag}
        onTouchStart={drawMode ? undefined : handleTouchStart}
        onTouchMove={drawMode ? undefined : handleTouchMove}
        onTouchEnd={drawMode ? undefined : stopDrag}
        style={{ cursor: drawMode ? 'crosshair' : zoom > 1 ? (isDragging.current ? 'grabbing' : 'grab') : 'default' }}
      >
        <div
          key={id}
          className={`relative flex items-center justify-center w-full h-full${
            navDirection === 'next' ? ' photo-slide-next' :
            navDirection === 'prev' ? ' photo-slide-prev' : ''
          }`}
          style={{
            transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
            transformOrigin: 'center',
            transition: isDragging.current ? 'none' : 'transform 0.15s ease',
            userSelect: 'none',
            pointerEvents: 'none',
          }}
        >
          {/* sm thumbnail: cached from the grid → renders synchronously, eliminates black flash */}
          <AuthImage
            src={getThumbnailUrl(photo.id, 'sm')}
            alt=""
            className="absolute inset-0 w-full h-full object-contain select-none"
            style={{ filter: 'blur(14px)', transform: 'scale(1.06)', opacity: imgLoaded ? 0 : 1, transition: 'opacity 0.15s ease' } as React.CSSProperties}
            loading="eager"
          />
          {/* lg thumbnail: 1600px — shown sharp as the visible placeholder until original loads */}
          <AuthImage
            src={getThumbnailUrl(photo.id, 'lg')}
            alt=""
            className="absolute inset-0 w-full h-full object-contain select-none"
            style={{ opacity: imgLoaded ? 0 : 1, transition: 'opacity 0.2s ease' } as React.CSSProperties}
            loading="eager"
          />
          <AuthImage
            ref={imgRef}
            src={getOriginalUrl(photo.id)}
            alt={photo.file_name}
            className="block max-h-full max-w-full object-contain select-none relative"
            loading="eager"
            onLoad={() => setImgLoaded(true)}
            style={{ opacity: imgLoaded ? 1 : 0, transition: 'opacity 0.15s ease' } as React.CSSProperties}
          />
        </div>

        {/* Draw-mode canvas overlay */}
        {drawMode && (
          <canvas
            ref={canvasRef}
            className="absolute inset-0 z-30"
            style={{ cursor: 'crosshair' }}
            onMouseDown={handleCanvasMouseDown}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={handleCanvasMouseUp}
            onMouseLeave={handleCanvasMouseUp}
          />
        )}

        {/* Draw-mode toolbar */}
        {drawMode && (
          <div className="absolute top-4 left-1/2 z-40 -translate-x-1/2 flex items-center gap-2 rounded-full bg-black/80 px-4 py-2 text-sm text-white backdrop-blur-sm">
            <svg className="h-4 w-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z" />
            </svg>
            <span>Drag to draw a box around the face</span>
            {drawRect && drawRect.w > 10 && drawRect.h > 10 && (
              <button
                onClick={handleConfirmFace}
                disabled={submittingFace}
                className="ml-2 rounded-full bg-blue-600 px-3 py-0.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {submittingFace ? 'Submitting…' : '✓ Confirm'}
              </button>
            )}
            <button
              onClick={exitDrawMode}
              className="ml-1 rounded-full bg-white/10 px-3 py-0.5 text-xs hover:bg-white/20"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Zoom toolbar */}
        <div className="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-full bg-black/60 px-3 py-1.5 backdrop-blur-sm">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= ZOOM_MIN}
            aria-label="Zoom out"
            className="rounded-full p-1.5 text-white hover:bg-white/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16zM8 11h6" />
            </svg>
          </button>
          <button
            onClick={handleZoomReset}
            aria-label="Reset zoom"
            className="min-w-[3rem] rounded-full px-2 py-0.5 text-xs font-medium text-white hover:bg-white/20"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= ZOOM_MAX}
            aria-label="Zoom in"
            className="rounded-full p-1.5 text-white hover:bg-white/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16zM11 8v6M8 11h6" />
            </svg>
          </button>
        </div>

        {/* Photo counter */}
        {currentIndex !== -1 && navPhotoIds.length > 0 && (
          <div className="absolute bottom-4 right-4 z-20 rounded-full bg-black/50 px-3 py-1 text-xs text-white">
            {currentIndex + 1} / {navPhotoIds.length}
          </div>
        )}
      </div>

      {/* Metadata sidebar */}
      {showInfo && (
        <aside className="w-80 flex-shrink-0 overflow-y-auto bg-gray-900 p-6 text-white">
          <h2 className="mb-4 text-lg font-semibold">{photo.file_name}</h2>

          {/* Date */}
          {photo.taken_at && (
            <InfoSection title="Date">
              <p>{format(new Date(photo.taken_at), 'EEEE, MMMM d, yyyy')}</p>
              <p className="text-sm text-gray-400">{format(new Date(photo.taken_at), 'h:mm a')}</p>
            </InfoSection>
          )}

          {/* Location */}
          {photo.gps_latitude != null && photo.gps_longitude != null && (
            <InfoSection title="Location">
              {photo.location_name && (
                <p className="text-sm font-medium text-gray-200 mb-1">{photo.location_name}</p>
              )}
              <p className="text-sm text-gray-400">
                {photo.gps_latitude.toFixed(6)}, {photo.gps_longitude.toFixed(6)}
              </p>
              <div className="mt-2 h-32 rounded-lg overflow-hidden bg-gray-800">
                <img
                  src={`https://tile.openstreetmap.org/15/${lonToTile(photo.gps_longitude, 15)}/${latToTile(photo.gps_latitude, 15)}.png`}
                  alt="Map"
                  className="h-full w-full object-cover opacity-70"
                />
              </div>
            </InfoSection>
          )}

          {/* Camera */}
          {(photo.camera_make || photo.camera_model) && (
            <InfoSection title="Camera">
              <p>{[photo.camera_make, photo.camera_model].filter(Boolean).join(' ')}</p>
              {photo.lens_model && <p className="text-sm text-gray-400">{photo.lens_model}</p>}
            </InfoSection>
          )}

          {/* Exposure */}
          {(photo.f_number || photo.exposure_time || photo.iso || photo.focal_length) && (
            <InfoSection title="Exposure">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {photo.f_number && (
                  <div>
                    <span className="text-gray-400">f/</span>
                    {photo.f_number}
                  </div>
                )}
                {photo.exposure_time && (
                  <div>
                    <span className="text-gray-400">Shutter: </span>
                    {photo.exposure_time}
                  </div>
                )}
                {photo.iso && (
                  <div>
                    <span className="text-gray-400">ISO </span>
                    {photo.iso}
                  </div>
                )}
                {photo.focal_length && (
                  <div>
                    <span className="text-gray-400">FL: </span>
                    {photo.focal_length}mm
                  </div>
                )}
              </div>
            </InfoSection>
          )}

          {/* Dimensions */}
          <InfoSection title="Details">
            <div className="space-y-1 text-sm">
              {photo.width && photo.height && (
                <p>{photo.width} × {photo.height}</p>
              )}
              <p>{formatFileSize(photo.file_size)}</p>
              <p className="text-gray-400">{photo.mime_type}</p>
              <div className="mt-2 pt-2 border-t border-gray-700">
                <p className="text-xs text-gray-500 mb-0.5">File path</p>
                <p className="text-xs text-gray-400 break-all font-mono">{photo.host_file_path ?? `/mnt/photos/${photo.file_path}`}</p>
              </div>
            </div>
          </InfoSection>

          {/* Scan for faces */}
          <InfoSection title="Face Detection">
            <button
              onClick={handleScanFaces}
              disabled={scanningFaces || drawMode}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {scanningFaces ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Scanning…
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.82V15a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
                  </svg>
                  Scan for Faces
                </>
              )}
            </button>

            <button
              onClick={drawMode ? exitDrawMode : enterDrawMode}
              className={`mt-2 flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm ${
                drawMode
                  ? 'bg-blue-700 text-white hover:bg-blue-600'
                  : 'bg-gray-800 text-gray-200 hover:bg-gray-700'
              }`}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z" />
              </svg>
              {drawMode ? 'Cancel Drawing' : 'Draw Face Region'}
            </button>

            {photoFaces.length === 0 && (
              <p className="mt-1.5 text-xs text-gray-500">No faces detected yet. Try scanning or draw a region manually.</p>
            )}
          </InfoSection>

          {/* Faces detected */}
          {photoFaces.length > 0 && (
            <InfoSection title={`Faces (${photoFaces.length})`}>
              <div className="space-y-3">
                {photoFaces.map((face) => {
                  const person = people.find((p) => p.id === face.person_id);
                  const isAssigning = assigningFaceId === face.id;
                  return (
                    <div key={face.id} className="rounded-lg bg-gray-800 p-2">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 flex-shrink-0 overflow-hidden rounded-full bg-gray-700">
                          <AuthImage
                            src={getFaceThumbnailUrl(face.id, 80)}
                            alt="Face"
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-200 truncate">
                            {person?.name || 'Unnamed'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(face.confidence * 100).toFixed(0)}% confidence
                          </p>
                        </div>
                        <button
                          onClick={() => { setAssigningFaceId(isAssigning ? null : face.id); setNewPersonName(''); }}
                          className="rounded px-2 py-1 text-xs text-primary-400 hover:bg-gray-700"
                        >
                          {isAssigning ? 'Cancel' : person ? 'Change' : 'Name'}
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Delete this face?')) {
                              deleteFaceMutation.mutate(face.id);
                            }
                          }}
                          disabled={deleteFaceMutation.isPending}
                          title="Delete face"
                          className="rounded p-1 text-gray-500 hover:bg-gray-700 hover:text-red-400 disabled:opacity-50"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>

                      {/* Assign dropdown */}
                      {isAssigning && (
                        <div className="mt-2 space-y-2">
                          {/* Create new person */}
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              if (newPersonName.trim()) {
                                assignMutation.mutate({ faceId: face.id, new_person_name: newPersonName.trim() });
                              }
                            }}
                            className="flex gap-1"
                          >
                            <input
                              value={newPersonName}
                              onChange={(e) => setNewPersonName(e.target.value)}
                              placeholder="Enter name..."
                              className="flex-1 rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white placeholder-gray-400 focus:border-primary-500 focus:outline-none"
                              autoFocus
                            />
                            <button
                              type="submit"
                              disabled={!newPersonName.trim() || assignMutation.isPending}
                              className="rounded bg-primary-600 px-2 py-1 text-xs text-white hover:bg-primary-700 disabled:opacity-50"
                            >
                              Add
                            </button>
                          </form>

                          {/* Or assign to existing person */}
                          {people.length > 0 && (
                            <div className="max-h-32 overflow-y-auto rounded border border-gray-700">
                              <p className="px-2 py-1 text-xs text-gray-500">Or assign to existing:</p>
                              {people
                                .filter((p) => p.id !== face.person_id)
                                .map((p) => (
                                  <button
                                    key={p.id}
                                    onClick={() => assignMutation.mutate({ faceId: face.id, person_id: p.id })}
                                    disabled={assignMutation.isPending}
                                    className="flex w-full items-center gap-2 px-2 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                                  >
                                    <span className="truncate">{p.name || `Person (${p.face_count} faces)`}</span>
                                  </button>
                                ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </InfoSection>
          )}

          {/* Add to Album */}
          <InfoSection title="Albums">
            <div className="relative">
              <button
                onClick={() => setShowAlbumPicker(!showAlbumPicker)}
                className="flex w-full items-center gap-2 rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add to Album
              </button>
              {showAlbumPicker && (
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg bg-gray-800 border border-gray-700">
                  {albums.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-gray-400">No albums yet</p>
                  ) : (
                    albums.map((album) => (
                      <button
                        key={album.id}
                        onClick={() => addToAlbumMutation.mutate(album.id)}
                        disabled={addToAlbumMutation.isPending}
                        className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                      >
                        <span>📁</span>
                        <span className="truncate">{album.name}</span>
                        <span className="ml-auto text-xs text-gray-500">{album.photo_count}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </InfoSection>

          {/* Thumbnail preview */}
          <InfoSection title="Thumbnail">
            <div className="h-24 w-24 overflow-hidden rounded-lg">
              <AuthImage
                src={getThumbnailUrl(photo.id, 'sm')}
                alt="thumb"
                className="h-full w-full object-cover"
              />
            </div>
          </InfoSection>
        </aside>
      )}
    </div>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">{title}</h3>
      {children}
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function lonToTile(lon: number, zoom: number): number {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, zoom));
}

function latToTile(lat: number, zoom: number): number {
  return Math.floor(
    ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) *
      Math.pow(2, zoom),
  );
}
