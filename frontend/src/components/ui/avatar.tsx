import * as React from "react";
import { cn } from "@/lib/utils";

const Avatar = React.forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement>>(({ className, ...props }, ref) => <span ref={ref} className={cn("relative flex size-10 shrink-0 overflow-hidden rounded-full", className)} {...props} />);
Avatar.displayName = "Avatar";
const AvatarImage = React.forwardRef<HTMLImageElement, React.ImgHTMLAttributes<HTMLImageElement>>(({ alt, className, ...props }, ref) => (
  // Avatar images are intentionally unoptimized so this primitive can accept arbitrary image sources.
  // eslint-disable-next-line @next/next/no-img-element
  <img ref={ref} alt={alt ?? ""} className={cn("aspect-square size-full object-cover", className)} {...props} />
));
AvatarImage.displayName = "AvatarImage";
const AvatarFallback = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => <span className={cn("flex size-full items-center justify-center rounded-full bg-muted text-sm font-medium text-muted-foreground", className)} {...props} />;
export { Avatar, AvatarImage, AvatarFallback };
