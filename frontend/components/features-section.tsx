import { Search, Brain, Edit3, FileDown } from 'lucide-react';

const features = [
  {
    icon: Search,
    title: 'Search',
    description: 'Find real circuits from the web',
  },
  {
    icon: Brain,
    title: 'Understand',
    description: 'AI analyzes circuit topology',
  },
  {
    icon: Edit3,
    title: 'Edit',
    description: 'Modify circuits using prompts',
  },
  {
    icon: FileDown,
    title: 'Export',
    description: 'Generate LTspice .asc files',
  },
];

export function FeaturesSection() {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {features.map((feature, index) => {
        const Icon = feature.icon;
        return (
          <div
            key={index}
            className="group relative overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-white/0 p-4 hover:border-indigo-500/50 transition-all duration-300"
          >
            {/* Hover glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/0 to-purple-500/0 group-hover:from-indigo-500/10 group-hover:to-purple-500/10 transition-all duration-300" />

            <div className="relative z-10 space-y-3">
              <div className="inline-block rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-500/20 p-2">
                <Icon className="h-5 w-5 text-indigo-400" />
              </div>
              <h3 className="font-semibold text-white text-sm">{feature.title}</h3>
              <p className="text-xs text-gray-400">{feature.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
