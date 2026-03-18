import { Component, DestroyRef, ElementRef, inject, input, OnInit, viewChild } from "@angular/core";

@Component({
  selector: "app-jumping-text",
  templateUrl: "./jumping-text.component.html",
  styleUrl: "./jumping-text.component.scss",
})
export class JumpingTextComponent implements OnInit {
  text = input.required<string>();
  interval = input(4000);

  private readonly destroyRef = inject(DestroyRef);
  private readonly containerRef = viewChild<ElementRef>("container");
  private autoWaveTimer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.autoWaveTimer = setInterval(() => this.triggerWave(), this.interval());
    this.destroyRef.onDestroy(() => clearInterval(this.autoWaveTimer));
  }

  triggerWave(): void {
    const container = this.containerRef()?.nativeElement as HTMLElement | undefined;
    if (!container) return;
    const letters = container.querySelectorAll(".letter");
    letters.forEach((letter, i) => {
      const el = letter as HTMLElement;
      setTimeout(() => {
        const current = getComputedStyle(el).transform;
        const currentY = current !== "none" ? new DOMMatrix(current).m42 : 0;
        el.getAnimations().forEach((a) => a.cancel());
        el.animate(
          [
            { transform: `translateY(${currentY}px)`, easing: "cubic-bezier(0.33, 1, 0.68, 1)" },
            {
              transform: "translateY(-8px)",
              offset: 0.3,
              easing: "cubic-bezier(0.34, 1.56, 0.64, 1)",
            },
            {
              transform: "translateY(2px)",
              offset: 0.65,
              easing: "cubic-bezier(0.33, 1, 0.68, 1)",
            },
            { transform: "translateY(-2px)", offset: 0.82, easing: "ease-in-out" },
            { transform: "translateY(0)" },
          ],
          { duration: 800 },
        );
      }, i * 50);
    });
  }
}
