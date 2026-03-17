interface Props {
  title: string;
  description?: string;
  icon?: string;
}

export default function EmptyState({ title, description, icon = '📭' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-5xl">{icon}</span>
      <h3 className="mt-4 text-lg font-medium text-gray-900">{title}</h3>
      {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
    </div>
  );
}
