import * as SliderPrimitive from "@radix-ui/react-slider";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & { rangeColor?: string }
>(({ className, rangeColor, ...props }, ref) => (
  <SliderPrimitive.Root ref={ref} className={cn("relative flex w-full touch-none select-none items-center py-1.5", className)} {...props}>
    <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-line">
      <SliderPrimitive.Range className="absolute h-full bg-accent" style={rangeColor ? { background: rangeColor } : undefined} />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      aria-label={props["aria-label"]}
      className="block h-4 w-4 rounded-full border-2 border-accent bg-bg shadow transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
      style={rangeColor ? { borderColor: rangeColor } : undefined}
    />
  </SliderPrimitive.Root>
));
Slider.displayName = "Slider";
