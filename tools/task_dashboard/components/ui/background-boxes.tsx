'use client';
import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export const Boxes = ({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) => {
  const rows = new Array(150).fill(1);
  const cols = new Array(100).fill(1);

  // Theme colors: Blue (#3b82f6), Purple (#8b5cf6), Rose (#ec4899)
  const colors = [
    "rgb(59 130 246)",    // Blue
    "rgb(139 92 246)",    // Purple
    "rgb(236 72 153)",    // Rose
    "rgb(96 165 250)",    // Light Blue
    "rgb(168 85 247)",    // Light Purple
    "rgb(244 114 182)",   // Light Rose
  ];

  const getRandomColor = () => {
    return colors[Math.floor(Math.random() * colors.length)];
  };

  return (
    <div
      style={{
        transform: `translate(-40%,-60%) skewX(-48deg) skewY(14deg) scale(0.675) rotate(0deg) translateZ(0)`,
      }}
      className={cn(
        "absolute left-1/4 p-4 -top-1/4 flex -translate-x-1/2 -translate-y-1/2 w-full h-full z-0",
        className
      )}
      {...rest}
    >
      {rows.map((_, i) => (
        <motion.div
          key={`row` + i}
          className="w-16 h-8 border-l border-slate-700 relative"
        >
          {cols.map((_, j) => (
            <motion.div
              whileHover={{
                backgroundColor: getRandomColor(),
                transition: { duration: 0 },
              }}
              animate={{
                transition: { duration: 2 },
              }}
              key={`col` + j}
              className="w-16 h-8 border-r border-t border-slate-700 relative"
            >
            </motion.div>
          ))}
        </motion.div>
      ))}
    </div>
  );
};

export const BoxesCore = ({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) => {
  return (
    <div className={cn("h-full w-full absolute overflow-hidden", className)} {...rest}>
      <Boxes />
    </div>
  );
};
