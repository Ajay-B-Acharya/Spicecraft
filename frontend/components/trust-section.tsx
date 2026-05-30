import { Zap, Shield, Cpu, Wand2 } from 'lucide-react';

const trustItems = [
  {
    icon: Zap,
    title: 'AI Powered',
    description: 'Smarter circuit discovery',
    color: 'from-yellow-500 to-orange-500',
  },
  {
    icon: Shield,
    title: 'Real Circuits',
    description: 'Based on existing designs',
    color: 'from-cyan-500 to-blue-500',
  },
  {
    icon: Cpu,
    title: 'LTspice Ready',
    description: 'Export and simulate instantly',
    color: 'from-purple-500 to-indigo-500',
  },
  {
    icon: Wand2,
    title: 'Prompt Editing',
    description: 'Modify circuits naturally',
    color: 'from-pink-500 to-rose-500',
  },
];

export function TrustSection() {
  return (
    <section className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4">
          {trustItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                className="flex flex-col items-center text-center space-y-4 group"
              >
                <div className={`rounded-2xl bg-gradient-to-br ${item.color} p-4 group-hover:scale-110 transition-transform duration-300`}>
                  <Icon className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                <p className="text-sm text-gray-400">{item.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
