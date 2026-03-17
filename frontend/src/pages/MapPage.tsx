import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useUIStore } from '../stores/uiStore';
import { useMapClusters, useMapPhotos } from '../hooks/useMap';
import { getThumbnailUrl } from '../api/photos';
import AuthImage from '../components/common/AuthImage';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { MapCluster } from '../api/map';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icons
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function createClusterIcon(count: number) {
  const size = count > 50 ? 50 : count > 10 ? 40 : 32;
  return L.divIcon({
    html: `<div style="
      background: #3b82f6;
      color: white;
      border-radius: 50%;
      width: ${size}px;
      height: ${size}px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: ${size > 40 ? 14 : 12}px;
      font-weight: 600;
      border: 2px solid white;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    ">${count}</div>`,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function MapEventHandler({ onBoundsChange }: {
  onBoundsChange: (zoom: number, bounds: { sw_lat: number; sw_lng: number; ne_lat: number; ne_lng: number }) => void;
}) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce so rapid pan/zoom gestures don't fire a new API call on every
  // animation frame — waits 150 ms after the last moveend before updating.
  const dispatch = useCallback((m: L.Map) => {
    const b = m.getBounds();
    if (!b.isValid()) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      onBoundsChange(m.getZoom(), {
        sw_lat: b.getSouthWest().lat,
        sw_lng: b.getSouthWest().lng,
        ne_lat: b.getNorthEast().lat,
        ne_lng: b.getNorthEast().lng,
      });
    }, 150);
  }, [onBoundsChange]);

  // Only moveend — Leaflet already fires moveend after every zoomend.
  const map = useMapEvents({
    moveend: (e) => dispatch(e.target as L.Map),
  });

  // Sync initial bounds once the map is ready.
  useEffect(() => {
    if (map) dispatch(map);
    return () => { if (timer.current) clearTimeout(timer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

// Calls invalidateSize() after the sidebar CSS transition completes so Leaflet
// recalculates tile positions when the container width changes.
function MapResizer() {
  const map = useMap();
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);

  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 210);
    return () => clearTimeout(timer);
  }, [map, sidebarOpen]);

  return null;
}

// When the user clicks a cluster, flies the map to that position at +2 zoom
// levels so the cluster naturally breaks into sub-clusters / single-photo pins.
function FlyToCluster({ cluster }: { cluster: MapCluster | null }) {
  const map = useMap();
  const prev = useRef<MapCluster | null>(null);

  useEffect(() => {
    if (!cluster) return;
    // Don't re-fly if the same cluster was already targeted.
    if (prev.current?.lat === cluster.lat && prev.current?.lng === cluster.lng) return;
    prev.current = cluster;
    const targetZoom = Math.min(map.getZoom() + 2, 18);
    map.flyTo([cluster.lat, cluster.lng], targetZoom, { duration: 0.6 });
  }, [cluster, map]);

  return null;
}

export default function MapPage() {
  const navigate = useNavigate();
  // Match the MapContainer initial zoom so the first cluster fetch uses the
  // correct zoom level — previously 5 diverged from the map's rendered zoom.
  const [zoom, setZoom] = useState(10);
  const [bounds, setBounds] = useState<{ sw_lat: number; sw_lng: number; ne_lat: number; ne_lng: number } | undefined>();
  const [selectedCluster, setSelectedCluster] = useState<MapCluster | null>(null);

  const { data: clusters, isLoading } = useMapClusters(zoom, bounds);
  const { data: clusterPhotos } = useMapPhotos(
    selectedCluster?.lat ?? 0,
    selectedCluster?.lng ?? 0,
    zoom > 12 ? 5 : zoom > 8 ? 20 : 50,
  );

  const handleBoundsChange = useCallback((newZoom: number, newBounds: typeof bounds) => {
    setZoom(newZoom);
    setBounds(newBounds);
  }, []);

  const totalPhotos = useMemo(() => clusters?.reduce((s, c) => s + c.count, 0) ?? 0, [clusters]);

  const center = useMemo<[number, number]>(() => {
    if (clusters && clusters.length > 0) {
      const avgLat = clusters.reduce((s, c) => s + c.lat * c.count, 0) / totalPhotos;
      const avgLng = clusters.reduce((s, c) => s + c.lng * c.count, 0) / totalPhotos;
      return [avgLat, avgLng];
    }
    return [20, 0];
  }, [clusters, totalPhotos]);

  if (isLoading && !clusters) return <Spinner />;

  return (
    <div className="h-full">
      <h1 className="mb-4 text-xl font-semibold text-gray-900">
        Map
        {totalPhotos > 0 && (
          <span className="ml-2 text-sm font-normal text-gray-500">{totalPhotos} geotagged photos</span>
        )}
      </h1>

      <div className="h-[calc(100vh-10rem)] overflow-hidden rounded-xl shadow-sm">
        <MapContainer
          center={center}
          zoom={clusters && clusters.length > 0 ? 10 : 3}
          className="h-full w-full"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapEventHandler onBoundsChange={handleBoundsChange} />
          <MapResizer />
          <FlyToCluster cluster={selectedCluster} />

          {clusters?.map((cluster) =>
            cluster.count === 1 ? (
              // Single-photo pin — use lat,lng as stable key so React reuses
              // the marker across re-renders instead of recreating it.
              <Marker
                key={`${cluster.lat},${cluster.lng}`}
                position={[cluster.lat, cluster.lng]}
              >
                <Popup>
                  <div className="w-40">
                    <button
                      onClick={() => navigate(`/photo/${cluster.preview_photo_id}`)}
                      className="block w-full cursor-pointer"
                    >
                      <div className="h-28 w-full overflow-hidden rounded-lg bg-gray-200">
                        <AuthImage
                          src={getThumbnailUrl(cluster.preview_photo_id, 'sm')}
                          alt="Photo"
                          className="h-full w-full object-cover"
                        />
                      </div>
                      {cluster.location_label && (
                        <p className="mt-1 truncate text-xs text-gray-500">{cluster.location_label}</p>
                      )}
                    </button>
                  </div>
                </Popup>
              </Marker>
            ) : (
              // Cluster pin — clicking it flies the map to +2 zoom so the
              // cluster breaks apart into individual photo markers.
              <Marker
                key={`${cluster.lat},${cluster.lng}`}
                position={[cluster.lat, cluster.lng]}
                icon={createClusterIcon(cluster.count)}
                eventHandlers={{
                  click: () => setSelectedCluster(cluster),
                }}
              >
                <Popup>
                  <div className="w-48">
                    <p className="font-semibold text-sm mb-1">
                      {cluster.count} photos
                      {cluster.location_label && (
                        <span className="font-normal text-gray-500"> — {cluster.location_label}</span>
                      )}
                    </p>
                    {clusterPhotos &&
                    selectedCluster?.lat === cluster.lat &&
                    selectedCluster?.lng === cluster.lng ? (
                      <div className="grid grid-cols-3 gap-1 mt-2">
                        {clusterPhotos.slice(0, 6).map((p) => (
                          <button
                            key={p.id}
                            onClick={() => navigate(`/photo/${p.id}`)}
                            className="cursor-pointer"
                          >
                            <div className="h-14 w-full overflow-hidden rounded bg-gray-200">
                              <AuthImage
                                src={getThumbnailUrl(p.id, 'sm')}
                                alt={p.file_name}
                                className="h-full w-full object-cover"
                              />
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 mt-1">Zooming in to show photos…</p>
                    )}
                  </div>
                </Popup>
              </Marker>
            ),
          )}
        </MapContainer>
      </div>

      {clusters && clusters.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title="No geotagged photos"
            description="Photos with GPS coordinates will appear on the map"
            icon="🗺️"
          />
        </div>
      )}
    </div>
  );
}
