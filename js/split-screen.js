/* ==========================================================================
   AGENTREADY - Interactive Split-Screen Controller (Human vs AI View)
   ========================================================================== */

export class SplitScreenViewer {
  constructor() {
    this.container = document.getElementById('split-viewer-box');
    this.aiSide = document.getElementById('viewer-ai-side');
    this.handle = document.getElementById('split-handle');
    this.handleBtn = this.handle ? this.handle.querySelector('.handle-button') : null;

    this.isDragging = false;
    this.isAutoAnimating = false;
    this.isHovered = false;
    this.animFrameId = null;
    this.currentPercentage = 50;
    this.cycleDuration = 6000; // 6s cycle aller-retour lent
    this.center = 50;
    this.amplitude = 50; // oscillation entre 0% et 100%
    this.virtualTime = 0;
    this.lastTimestamp = null;

    if (!this.container || !this.aiSide || !this.handle) return;

    this.updateSliderWidth();
    window.addEventListener('resize', () => this.updateSliderWidth());
    this.initEvents();
    // Démarrage immédiat sans dépendance bloquante
    this.startAutoAnimation();
  }

  updateSliderWidth() {
    if (this.container) {
      this.container.style.setProperty('--slider-width', `${this.container.clientWidth}px`);
    }
  }

  startAutoAnimation() {
    if (this.isAutoAnimating) return;
    this.isAutoAnimating = true;
    this.lastTimestamp = null;

    if (this.handleBtn) {
      this.handleBtn.classList.add('is-auto-animating');
    }

    const loop = (now) => {
      if (!this.isAutoAnimating) return;

      if (this.lastTimestamp !== null) {
        const delta = now - this.lastTimestamp;
        // L'animation avance seulement si la souris n'est PAS dans le cadre et qu'on ne drag pas
        if (!this.isHovered && !this.isDragging) {
          this.virtualTime += delta;
          const progress = (this.virtualTime % this.cycleDuration) / this.cycleDuration;
          const angle = progress * Math.PI * 2;
          const pct = this.center + this.amplitude * Math.sin(angle);
          this.setPercentage(pct);
        }
      }

      this.lastTimestamp = now;
      this.animFrameId = requestAnimationFrame(loop);
    };

    this.animFrameId = requestAnimationFrame(loop);
  }

  stopAutoAnimation() {
    this.isAutoAnimating = false;
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.handleBtn) {
      this.handleBtn.classList.remove('is-auto-animating');
    }
  }

  setPercentage(pct) {
    const clamped = Math.max(0, Math.min(100, pct));
    this.currentPercentage = clamped;
    this.aiSide.style.width = `${clamped}%`;
    this.handle.style.left = `${clamped}%`;
    this.handle.setAttribute('aria-valuenow', Math.round(clamped));
  }

  syncVirtualTime() {
    const clampedRatio = Math.max(-1, Math.min(1, (this.currentPercentage - this.center) / this.amplitude));
    const angle = Math.asin(clampedRatio);
    this.virtualTime = (angle / (Math.PI * 2)) * this.cycleDuration;
    if (this.virtualTime < 0) this.virtualTime += this.cycleDuration;
  }

  initEvents() {
    // 1. SURVOL : Dès que la souris entre dans le cadre -> on fige instantanément l'oscillation et on donne la main !
    this.container.addEventListener('mouseenter', () => {
      this.isHovered = true;
      if (this.handleBtn) {
        this.handleBtn.classList.remove('is-auto-animating');
      }
    });

    // 2. SORTIE : Dès que la souris quitte le cadre -> l'oscillation reprend doucement et sans à-coup !
    this.container.addEventListener('mouseleave', () => {
      this.isHovered = false;
      this.isDragging = false;
      if (this.handleBtn) {
        this.handleBtn.classList.add('is-auto-animating');
      }
    });

    // 3. GLISSER-DÉPOSER DE LA FLÈCHE (Souris)
    this.handle.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.isHovered = true;
      e.preventDefault();
      e.stopPropagation();
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      this.updatePosition(e.clientX);
    });

    // 4. ACCESSIBILITÉ CLAVIER (role="slider")
    this.handle.addEventListener('keydown', (e) => {
      let handled = false;
      let newPct = this.currentPercentage;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
        newPct = Math.max(0, this.currentPercentage - 5);
        handled = true;
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
        newPct = Math.min(100, this.currentPercentage + 5);
        handled = true;
      } else if (e.key === 'PageDown') {
        newPct = Math.max(0, this.currentPercentage - 20);
        handled = true;
      } else if (e.key === 'PageUp') {
        newPct = Math.min(100, this.currentPercentage + 20);
        handled = true;
      } else if (e.key === 'Home') {
        newPct = 0;
        handled = true;
      } else if (e.key === 'End') {
        newPct = 100;
        handled = true;
      }

      if (handled) {
        e.preventDefault();
        this.isHovered = true;
        this.stopAutoAnimation();
        this.setPercentage(newPct);
        this.syncVirtualTime();
      }
    });

    this.handle.addEventListener('focus', () => {
      this.isHovered = true;
      this.stopAutoAnimation();
    });

    this.handle.addEventListener('blur', () => {
      this.isHovered = false;
      this.startAutoAnimation();
    });

    // 5. TACTILE (Smartphones & Tablettes)
    this.container.addEventListener('touchstart', () => {
      this.isHovered = true;
    }, { passive: true });

    this.handle.addEventListener('touchstart', (e) => {
      this.isDragging = true;
      this.isHovered = true;
      e.stopPropagation();
    }, { passive: true });

    window.addEventListener('touchend', () => {
      this.isDragging = false;
      setTimeout(() => {
        this.isHovered = false;
      }, 2000);
    });

    window.addEventListener('touchmove', (e) => {
      if (!this.isDragging || !e.touches[0]) return;
      this.updatePosition(e.touches[0].clientX);
    }, { passive: true });

    // 6. CLIC DIRECT DANS LE CADRE : Positionne la flèche instantanément
    this.container.addEventListener('click', (e) => {
      if (e.target.closest('#split-handle')) return;
      this.updatePosition(e.clientX);
    });

    // 7. BOUTONS DE COMMUTATION RAPIDE (Mobile & Tablette)
    const btnHuman = document.getElementById('btn-split-show-human');
    const btnCenter = document.getElementById('btn-split-show-center');
    const btnAi = document.getElementById('btn-split-show-ai');
    const toggleButtons = [btnHuman, btnCenter, btnAi].filter(Boolean);

    const setActiveToggle = (activeBtn) => {
      toggleButtons.forEach(b => b.classList.remove('active'));
      if (activeBtn) activeBtn.classList.add('active');
    };

    if (btnHuman) {
      btnHuman.addEventListener('click', () => {
        this.stopAutoAnimation();
        this.setPercentage(0);
        this.syncVirtualTime();
        setActiveToggle(btnHuman);
      });
    }
    if (btnCenter) {
      btnCenter.addEventListener('click', () => {
        this.stopAutoAnimation();
        this.setPercentage(50);
        this.syncVirtualTime();
        setActiveToggle(btnCenter);
      });
    }
    if (btnAi) {
      btnAi.addEventListener('click', () => {
        this.stopAutoAnimation();
        this.setPercentage(100);
        this.syncVirtualTime();
        setActiveToggle(btnAi);
      });
    }
  }

  updatePosition(clientX) {
    const rect = this.container.getBoundingClientRect();
    const offsetX = clientX - rect.left;
    const percentage = (offsetX / rect.width) * 100;
    this.setPercentage(percentage);
    this.syncVirtualTime();
  }
}
