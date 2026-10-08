import { Badge } from '@/components/nexus/Badge';

type Props = {
  label: string;
};

export function AmbienteBadge({ label }: Props) {
  const isHomolog = label.toLowerCase().includes('homolog');
  return (
    <Badge variant={isHomolog ? 'info' : 'default'} className="hidden sm:inline-flex text-[10px] px-2 py-0 shrink-0">
      {label}
    </Badge>
  );
}
