import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  viewChild,
} from '@angular/core';
import type { ElementRef, OnInit } from '@angular/core';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-jumping-text',
  standalone: true,
  styleUrl: './jumping-text.component.scss',
  templateUrl: './jumping-text.component.html',
})
export class JumpingTextComponent implements OnInit {
  text = input.required<string>();
  interval = input(4000);

  private readonly destroyRef = inject(DestroyRef);
  private readonly containerRef = viewChild<ElementRef<HTMLElement>>('container');
  private autoWaveTimer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.autoWaveTimer = setInterval(() => {
      this.triggerWave();
    }, this.interval());
    this.destroyRef.onDestroy(() => {
      clearInterval(this.autoWaveTimer);
    });
  }

  triggerWave(): void {
    const container = this.containerRef()?.nativeElement;
    if (!container) {
      return;
    }
    const letters = container.querySelectorAll<HTMLElement>('.letter');
    letters.forEach((letter, i) => {
      setTimeout(() => {
        const current = getComputedStyle(letter).transform;
        const currentY = current !== 'none' ? new DOMMatrix(current).m42 : 0;
        letter.getAnimations().forEach((a) => {
          a.cancel();
        });
        letter.animate(
          [
            { easing: 'cubic-bezier(0.33, 1, 0.68, 1)', transform: `translateY(${currentY}px)` },
            {
              easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
              offset: 0.3,
              transform: 'translateY(-8px)',
            },
            {
              easing: 'cubic-bezier(0.33, 1, 0.68, 1)',
              offset: 0.65,
              transform: 'translateY(2px)',
            },
            { easing: 'ease-in-out', offset: 0.82, transform: 'translateY(-2px)' },
            { transform: 'translateY(0)' },
          ],
          { duration: 800 },
        );
      }, i * 50);
    });
  }
}
