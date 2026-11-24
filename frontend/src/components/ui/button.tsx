import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-accent text-bg hover:bg-accent-strong",
        outline: "border border-line bg-panel2 text-ink hover:bg-line",
        ghost: "text-ink-2 hover:bg-panel2 hover:text-ink",
        danger: "border border-sev-critical/50 text-sev-critical hover:bg-sev-critical/10",
      },
      size: {
        default: "h-9 px-3",
        sm: "h-8 px-2.5 text-xs",
        icon: "h-8 w-8",
      },
      active: { true: "bg-accent/15 text-accent border-accent/50", false: "" },
    },
    defaultVariants: { variant: "default", size: "default", active: false },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, active, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, active }), className)} ref={ref} {...props} />;
});
Button.displayName = "Button";
