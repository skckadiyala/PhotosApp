import { NavLink } from 'react-router-dom';
import { useUIStore } from '../../stores/uiStore';
import { clsx } from 'clsx';

const navItems = [
  { to: '/timeline', label: 'Timeline', icon: '📷' },
  { to: '/videos', label: 'Videos', icon: '🎬' },
  { to: '/albums', label: 'Albums', icon: '📁' },
  { to: '/people', label: 'People', icon: '👤' },
  { to: '/map', label: 'Map', icon: '🗺️' },
  { to: '/favorites', label: 'Favorites', icon: '❤️' },
];

export default function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);

  return (
    <aside
      className={clsx(
        'fixed left-0 top-0 z-30 flex h-full flex-col bg-white border-r border-gray-200 transition-all duration-200',
        sidebarOpen ? 'w-64' : 'w-16',
      )}
    >
      <div className="flex h-14 items-center gap-3 border-b border-gray-200 px-4">
        <span className="text-xl">📸</span>
        {sidebarOpen && (
          <span className="text-lg font-semibold text-gray-800">PhotosApp</span>
        )}
      </div>
      <nav className="flex-1 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
              )
            }
          >
            <span className="text-lg">{item.icon}</span>
            {sidebarOpen && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
