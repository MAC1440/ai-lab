import { Menubar as MenubarPrimitive } from "radix-ui";
import { CheckIcon, ChevronRightIcon, CircleIcon } from "lucide-react";
import { type ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Menubar({
  className,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Root>) {
  return (
    <MenubarPrimitive.Root
      data-slot="menubar"
      className={cn(
        "flex h-9 items-center gap-1 rounded-lg border border-border bg-surface p-1 shadow-xs dark:border-border dark:bg-surface-raised",
        className,
      )}
      {...props}
    />
  );
}

export function MenubarMenu({
  ...props
}: ComponentProps<typeof MenubarPrimitive.Menu>) {
  return <MenubarPrimitive.Menu data-slot="menubar-menu" {...props} />;
}

export function MenubarGroup({
  ...props
}: ComponentProps<typeof MenubarPrimitive.Group>) {
  return <MenubarPrimitive.Group data-slot="menubar-group" {...props} />;
}

export function MenubarPortal({
  ...props
}: ComponentProps<typeof MenubarPrimitive.Portal>) {
  return <MenubarPrimitive.Portal data-slot="menubar-portal" {...props} />;
}

export function MenubarTrigger({
  className,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Trigger>) {
  return (
    <MenubarPrimitive.Trigger
      data-slot="menubar-trigger"
      className={cn(
        "flex cursor-default select-none items-center rounded-md px-2 py-1 text-sm font-medium outline-none",
        "focus:bg-surface-hover focus:text-foreground data-[state=open]:bg-surface-hover data-[state=open]:text-foreground",
        "dark:focus:bg-surface-hover dark:focus:text-foreground dark:data-[state=open]:bg-surface-hover dark:data-[state=open]:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function MenubarContent({
  className,
  align = "start",
  alignOffset = -4,
  sideOffset = 8,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Content>) {
  return (
    <MenubarPortal>
      <MenubarPrimitive.Content
        data-slot="menubar-content"
        align={align}
        alignOffset={alignOffset}
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-[12rem] overflow-hidden rounded-lg border border-border bg-surface p-1 text-foreground shadow-md",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          "dark:border-border dark:bg-surface-raised dark:text-foreground",
          className,
        )}
        {...props}
      />
    </MenubarPortal>
  );
}

export function MenubarItem({
  className,
  inset,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Item> & {
  inset?: boolean;
}) {
  return (
    <MenubarPrimitive.Item
      data-slot="menubar-item"
      className={cn(
        "relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none",
        "focus:bg-surface-hover focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        "dark:focus:bg-surface-hover dark:focus:text-foreground",
        inset && "pl-8",
        className,
      )}
      {...props}
    />
  );
}

export function MenubarCheckboxItem({
  className,
  children,
  checked,
  ...props
}: ComponentProps<typeof MenubarPrimitive.CheckboxItem>) {
  return (
    <MenubarPrimitive.CheckboxItem
      data-slot="menubar-checkbox-item"
      className={cn(
        "relative flex cursor-default select-none items-center rounded-md py-1.5 pl-8 pr-2 text-sm outline-none",
        "focus:bg-surface-hover focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        "dark:focus:bg-surface-hover dark:focus:text-foreground",
        className,
      )}
      checked={checked}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <MenubarPrimitive.ItemIndicator>
          <CheckIcon className="size-4" />
        </MenubarPrimitive.ItemIndicator>
      </span>
      {children}
    </MenubarPrimitive.CheckboxItem>
  );
}

export function MenubarRadioGroup({
  ...props
}: ComponentProps<typeof MenubarPrimitive.RadioGroup>) {
  return (
    <MenubarPrimitive.RadioGroup data-slot="menubar-radio-group" {...props} />
  );
}

export function MenubarRadioItem({
  className,
  children,
  ...props
}: ComponentProps<typeof MenubarPrimitive.RadioItem>) {
  return (
    <MenubarPrimitive.RadioItem
      data-slot="menubar-radio-item"
      className={cn(
        "relative flex cursor-default select-none items-center rounded-md py-1.5 pl-8 pr-2 text-sm outline-none",
        "focus:bg-surface-hover focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        "dark:focus:bg-surface-hover dark:focus:text-foreground",
        className,
      )}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <MenubarPrimitive.ItemIndicator>
          <CircleIcon className="size-2 fill-current" />
        </MenubarPrimitive.ItemIndicator>
      </span>
      {children}
    </MenubarPrimitive.RadioItem>
  );
}

export function MenubarLabel({
  className,
  inset,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Label> & {
  inset?: boolean;
}) {
  return (
    <MenubarPrimitive.Label
      data-slot="menubar-label"
      className={cn(
        "px-2 py-1.5 text-sm font-semibold",
        inset && "pl-8",
        className,
      )}
      {...props}
    />
  );
}

export function MenubarSeparator({
  className,
  ...props
}: ComponentProps<typeof MenubarPrimitive.Separator>) {
  return (
    <MenubarPrimitive.Separator
      data-slot="menubar-separator"
      className={cn("-mx-1 my-1 h-px bg-surface-hover dark:bg-surface-hover", className)}
      {...props}
    />
  );
}

export function MenubarShortcut({
  className,
  ...props
}: ComponentProps<"span">) {
  return (
    <span
      data-slot="menubar-shortcut"
      className={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)}
      {...props}
    />
  );
}

export function MenubarSub({
  ...props
}: ComponentProps<typeof MenubarPrimitive.Sub>) {
  return <MenubarPrimitive.Sub data-slot="menubar-sub" {...props} />;
}

export function MenubarSubTrigger({
  className,
  inset,
  children,
  ...props
}: ComponentProps<typeof MenubarPrimitive.SubTrigger> & {
  inset?: boolean;
}) {
  return (
    <MenubarPrimitive.SubTrigger
      data-slot="menubar-sub-trigger"
      className={cn(
        "flex cursor-default select-none items-center rounded-md px-2 py-1.5 text-sm outline-none",
        "focus:bg-surface-hover focus:text-foreground data-[state=open]:bg-surface-hover data-[state=open]:text-foreground",
        "dark:focus:bg-surface-hover dark:focus:text-foreground dark:data-[state=open]:bg-surface-hover dark:data-[state=open]:text-foreground",
        inset && "pl-8",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronRightIcon className="ml-auto size-4" />
    </MenubarPrimitive.SubTrigger>
  );
}

export function MenubarSubContent({
  className,
  ...props
}: ComponentProps<typeof MenubarPrimitive.SubContent>) {
  return (
    <MenubarPrimitive.SubContent
      data-slot="menubar-sub-content"
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-lg border border-border bg-surface p-1 text-foreground shadow-lg",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        "dark:border-border dark:bg-surface-raised dark:text-foreground",
        className,
      )}
      {...props}
    />
  );
}
