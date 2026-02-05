'use client';

import { motion } from 'framer-motion';

export function BetaBadge() {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="fixed top-4 left-4 z-50"
    >
      <div className="flex items-center bg-black text-white px-4 py-2 rounded-full shadow-lg border border-gray-300">
        <span className="text-sm font-semibold tracking-wide">BETA</span>
      </div>
    </motion.div>
  );
}
