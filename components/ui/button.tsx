import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Modern, token-driven Button.
 *
 * Interaction model:
 *  - default : calm resting state with a soft layered shadow + inner top sheen
 *  - hover   : lifts 1px, deepens the shadow, brightens the surface
 *  - active  : presses down (translateY 0 + scale 0.97), shadow tightens
 *  - disabled: faded, no shadow, no motion, not-allowed cursor
 *
 * Icons passed as children are auto-sized to 1rem and never shrink,
 * so any <svg>/lucide icon aligns cleanly with the label.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold leading-none tracking-wide ' +
    'transition-all duration-200 ease-out select-none cursor-pointer ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ' +
    'active:scale-[0.97] ' +
    'disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none disabled:translate-y-0 disabled:scale-100 disabled:cursor-not-allowed ' +
    'motion-reduce:transition-none motion-reduce:hover:translate-y-0 motion-reduce:active:scale-100 ' +
    '[&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground ' +
          'shadow-[0_1px_2px_rgb(0_0_0_/_0.08),inset_0_1px_0_rgb(255_255_255_/_0.12)] ' +
          'hover:bg-primary/90 hover:-translate-y-px ' +
          'hover:shadow-[0_8px_20px_rgb(0_0_0_/_0.18),inset_0_1px_0_rgb(255_255_255_/_0.12)] ' +
          'active:translate-y-0 active:shadow-[0_1px_2px_rgb(0_0_0_/_0.10)]',
        destructive:
          'bg-destructive text-destructive-foreground ' +
          'shadow-[0_1px_2px_rgb(0_0_0_/_0.08),inset_0_1px_0_rgb(255_255_255_/_0.18)] ' +
          'hover:bg-destructive/90 hover:-translate-y-px ' +
          'hover:shadow-[0_8px_20px_rgb(239_68_68_/_0.35),inset_0_1px_0_rgb(255_255_255_/_0.18)] ' +
          'active:translate-y-0 active:shadow-[0_1px_2px_rgb(0_0_0_/_0.10)]',
        outline:
          'border border-input bg-background text-foreground shadow-sm ' +
          'hover:bg-accent hover:text-accent-foreground hover:-translate-y-px hover:shadow-md ' +
          'active:translate-y-0 active:shadow-sm',
        secondary:
          'bg-secondary text-secondary-foreground shadow-sm ' +
          'hover:bg-secondary/80 hover:-translate-y-px hover:shadow-md ' +
          'active:translate-y-0 active:shadow-sm',
        ghost:
          'hover:bg-accent hover:text-accent-foreground hover:-translate-y-px ' +
          'active:translate-y-0',
        link:
          'text-primary underline-offset-4 hover:underline hover:-translate-y-px ' +
          'active:translate-y-0',
      },
      size: {
        default: 'h-10 px-5 min-w-[40px]',
        sm: 'h-9 px-3.5 text-xs',
        lg: 'h-11 px-7 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = 'button', ...props }, ref) => {
    return (
      <button
        type={type}
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
