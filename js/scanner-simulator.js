/* ==========================================================================
   AGENTREADY - Scanner Simulator Engine
   ========================================================================== */

import { AUDIT_PRESETS } from './mock-data.js';

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}


export class ScannerSimulator {
  constructor() {
    this.form = document.getElementById('scanner-form');
    this.input = document.getElementById('scanner-url-input');
    this.progressBox = document.getElementById('scan-progress-box');
    this.progressBar = document.getElementById('scan-progress-fill');
    this.progressStatus = document.getElementById('scan-progress-text');
    this.stepsList = document.querySelectorAll('.scan-step-item');
    this.resultsCard = document.getElementById('audit-results-card');

    // Scan error banner (TACHE-03 UX)
    this.errorBox = document.getElementById('scan-error-box');
    this.errorHead = document.getElementById('scan-error-head');
    this.errorTitle = document.getElementById('scan-error-title');
    this.errorMessage = document.getElementById('scan-error-message');
    this.btnRetryScanError = document.getElementById('btn-retry-scan-error');
    this.errorContact = document.getElementById('scan-error-contact');
    this.lastScannedUrl = '';
    
    // Result elements
    this.scoreNumber = document.getElementById('gauge-score-val');
    this.gaugeCircle = document.getElementById('gauge-circle-fill');
    this.statusBadge = document.getElementById('audit-status-badge');
    this.domainTitle = document.getElementById('audit-domain-title');
    this.domainUrl = document.getElementById('audit-domain-url');
    this.auditSummary = document.getElementById('audit-summary-text');
    
    // Pillars elements
    this.crawlScore = document.getElementById('pillar-score-crawl');
    this.crawlStatus = document.getElementById('pillar-status-crawl');
    this.schemaScore = document.getElementById('pillar-score-schema');
    this.schemaStatus = document.getElementById('pillar-status-schema');
    this.tokensScore = document.getElementById('pillar-score-tokens');
    this.tokensStatus = document.getElementById('pillar-status-tokens');
    this.simScore = document.getElementById('pillar-score-sim');
    this.simStatus = document.getElementById('pillar-status-sim');
    this.protoScore = document.getElementById('pillar-score-proto');
    this.protoStatus = document.getElementById('pillar-status-proto');

    // What's Broken & Inline Auto-Fix elements
    this.headerScore = document.getElementById('header-score-number');
    this.whatsBrokenList = document.getElementById('whats-broken-list');
    this.brokenCountBadge = document.getElementById('broken-count-badge');
    this.inlineCode = document.getElementById('inline-autofix-code');
    this.tabBefore = document.getElementById('btn-tab-before');
    this.tabAfter = document.getElementById('btn-tab-after');
    this.btnCopyInline = document.getElementById('btn-copy-inline-fix');
    this.currentInlineMode = 'after';

    this.isScanning = false;
    this.initEvents();
  }

  setInlineMode(mode) {
    this.currentInlineMode = mode;
    if (this.tabBefore) this.tabBefore.classList.toggle('active', mode === 'before');
    if (this.tabAfter) this.tabAfter.classList.toggle('active', mode === 'after');

    const data = window.__lastAuditData;
    if (!data || !this.inlineCode) return;

    if (mode === 'before') {
      this.inlineCode.textContent = data.rawJsonLd || '<!-- Aucun balisage JSON-LD détecté sur la page scannée -->';
      this.inlineCode.style.color = '#f87171';
    } else {
      const fixedCode = data.fixedJsonLd || data.autoFix?.schemaJson || '// JSON-LD réparé prêt à injecter';
      this.inlineCode.textContent = fixedCode;
      this.inlineCode.style.color = '#34d399';
    }
  }

  async copyInlineCode() {
    const data = window.__lastAuditData;
    if (!data) return;
    const codeToCopy = this.currentInlineMode === 'before' 
      ? (data.rawJsonLd || '') 
      : (data.fixedJsonLd || data.autoFix?.schemaJson || '');

    if (!codeToCopy) return;

    let success = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(codeToCopy);
        success = true;
      } else {
        throw new Error("Clipboard API unavailable");
      }
    } catch (err) {
      try {
        const textarea = document.createElement("textarea");
        textarea.value = codeToCopy;
        textarea.style.position = "fixed";
        textarea.style.left = "-999999px";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        success = document.execCommand("copy");
        document.body.removeChild(textarea);
      } catch (fallbackErr) {
        console.warn("Fallback copy failed:", fallbackErr);
      }
    }

    if (success && this.btnCopyInline) {
      const originalHtml = this.btnCopyInline.innerHTML;
      this.btnCopyInline.innerHTML = '<i class="fas fa-check"></i> Code copié !';
      this.btnCopyInline.style.background = 'var(--emerald-600)';
      setTimeout(() => {
        this.btnCopyInline.innerHTML = originalHtml;
        this.btnCopyInline.style.background = 'var(--emerald-500)';
      }, 2200);
    }
  }

  initEvents() {
    const handleScanTrigger = (e) => {
      if (e) e.preventDefault();
      const url = this.input ? this.input.value.trim() : '';
      this.runScan(url);
    };

    if (this.form) {
      this.form.addEventListener('submit', handleScanTrigger);
    }

    const btn = document.getElementById('btn-run-scan');
    if (btn) {
      btn.addEventListener('click', handleScanTrigger);
    }

    if (this.input) {
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          handleScanTrigger(e);
        }
      });
    }

    // Language Toggle
    const langBtnEn = document.getElementById('lang-btn-en');
    const langBtnFr = document.getElementById('lang-btn-fr');
    const heroTitle = document.getElementById('hero-main-title');
    const heroLead = document.getElementById('hero-main-lead');
    const btnRunScan = document.getElementById('btn-run-scan');
    const scannerSubtext = document.getElementById('scanner-subtext-label');
    const navCtaFix = document.getElementById('nav-cta-fix');

    if (langBtnEn && langBtnFr && heroTitle && heroLead) {
      langBtnEn.addEventListener('click', () => {
        document.documentElement.lang = 'en';
        langBtnEn.classList.add('active');
        langBtnEn.style.borderColor = 'var(--border-medium)';
        langBtnEn.style.color = '#fff';
        langBtnFr.classList.remove('active');
        langBtnFr.style.borderColor = 'var(--border-subtle)';
        langBtnFr.style.color = 'var(--text-muted)';
        heroTitle.innerHTML = `Your products are invisible to AI buyers. <br><span class="gradient-text">Fix them.</span>`;
        heroLead.textContent = `Get an instant, deterministic audit of how ChatGPT, Gemini and Claude see your store — then deploy clean JSON-LD and an llms.txt in one click. No AI judging your score. No guesswork.`;
        if (this.input) this.input.placeholder = "Enter your product or store URL (e.g. my-store.com/products/jacket)";
        if (btnRunScan) btnRunScan.innerHTML = `<i class="fas fa-bolt"></i> Fix my AI visibility`;
        if (scannerSubtext) scannerSubtext.textContent = '⚡ Free scan · No signup · 2 seconds · 100% Deterministic';
        if (navCtaFix) navCtaFix.innerHTML = `<i class="fas fa-wrench"></i> Fix AI Visibility`;
      });

      langBtnFr.addEventListener('click', () => {
        document.documentElement.lang = 'fr';
        langBtnFr.classList.add('active');
        langBtnFr.style.borderColor = 'var(--border-medium)';
        langBtnFr.style.color = '#fff';
        langBtnEn.classList.remove('active');
        langBtnEn.style.borderColor = 'var(--border-subtle)';
        langBtnEn.style.color = 'var(--text-muted)';
        heroTitle.innerHTML = `Vos produits sont invisibles pour les acheteurs IA. <br><span class="gradient-text">AgentReady les répare.</span>`;
        heroLead.textContent = `Audit 100% déterministe de la façon dont ChatGPT, Gemini et Claude voient votre boutique — correction déployable en un clic. Sans IA juge, sans spéculation.`;
        if (this.input) this.input.placeholder = "Entrez l'URL de votre produit ou boutique (ex: ma-boutique.fr/products/veste)";
        if (btnRunScan) btnRunScan.innerHTML = `<i class="fas fa-bolt"></i> Scanner ma boutique`;
        if (scannerSubtext) scannerSubtext.textContent = '⚡ Scan gratuit · Sans inscription · Résultat en 2 secondes · 100% Déterministe';
        if (navCtaFix) navCtaFix.innerHTML = `<i class="fas fa-wrench"></i> Corriger ma visibilité`;
      });
    }

    // Preset chips
    const chips = document.querySelectorAll('.preset-chip');
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const presetKey = chip.getAttribute('data-preset');
        if (AUDIT_PRESETS[presetKey]) {
          if (this.input) this.input.value = AUDIT_PRESETS[presetKey].domain;
          this.runScanWithPreset(presetKey);
        }
      });
    });

    // Inline Auto-Fix Tabs & Copy
    if (this.tabBefore) {
      this.tabBefore.addEventListener('click', () => this.setInlineMode('before'));
    }
    if (this.tabAfter) {
      this.tabAfter.addEventListener('click', () => this.setInlineMode('after'));
    }
    if (this.btnCopyInline) {
      this.btnCopyInline.addEventListener('click', () => this.copyInlineCode());
    }

    // Retry a failed scan from the error banner (TACHE-03 UX)
    if (this.btnRetryScanError) {
      this.btnRetryScanError.addEventListener('click', () => {
        if (this.isScanning) return;
        const url = this.lastScannedUrl || (this.input ? this.input.value.trim() : '');
        if (!url) return;
        if (this.input) this.input.value = url;
        this.runScan(url);
      });
    }
  }

  async runScan(customUrl) {
    if (this.isScanning) return;
    if (!customUrl || !customUrl.trim()) {
      if (this.input) {
        this.input.focus();
        this.input.classList.add('animate-shake');
        setTimeout(() => this.input.classList.remove('animate-shake'), 600);
      }
      return;
    }

    // Si l'utilisateur saisit explicitement l'une des 3 URLs des presets de démonstration
    const lower = customUrl.toLowerCase().trim();
    if (lower.includes('mystore-vintage.com')) {
      this.runScanWithPreset('blind');
      return;
    }
    if (lower.includes('urban-streetwear.fr')) {
      this.runScanWithPreset('friction');
      return;
    }
    if (lower.includes('sonus-audio.store')) {
      this.runScanWithPreset('ready');
      return;
    }

    // Real Live URL Scan via FastAPI Backend (relative URL works in local & Railway)
    this.isScanning = true;
    this.lastScannedUrl = customUrl.trim();
    this.hideScanError();
    this.startProgressUI();

    try {
      const geminiKey = (localStorage.getItem('agentready_gemini_key') || '').trim();
      const response = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: customUrl.trim(),
          geminiApiKey: geminiKey || undefined
        })
      });

      // TACHE-03 UX : Un refus explicite du backend (400/404/413/415/429/5xx) ne doit
      // PLUS être masqué par un faux résultat "friction". On affiche le message réel.
      if (!response.ok) {
        let statusInfo = `Erreur HTTP ${response.status}`;
        let backendDetail = '';
        try {
          const body = await response.json();
          if (body && typeof body.detail === 'string') backendDetail = body.detail;
        } catch (_e) { /* corps non-JSON, on garde statusInfo */ }
        this.completeProgressUI(() => {
          this.showScanError(response.status, backendDetail || statusInfo, customUrl.trim());
          this.isScanning = false;
        });
        return; // pas de fallback : une erreur backend est informative, pas un résultat
      }

      const realData = await response.json();
      this.completeProgressUI(() => {
        this.displayResults(realData);
        // Dispatch event for auto-fix code tabs
        window.dispatchEvent(new CustomEvent('agentready:scan-complete', { detail: realData }));
        this.isScanning = false;
      });

    } catch (err) {
      // Échec RÉSEAU réel (backend injoignable / hors-ligne) : pas d'erreur HTTP à montrer.
      // On garde un repli non-crash mais on le signale explicitement pour ne pas
      // faire passer ce scénario pour un véritable audit du site.
      console.warn('Backend unreachable, fallback démo transparent :', err);
      const cleanDomain = customUrl.trim().replace(/^https?:\/\//, '').split('/')[0];
      this.completeProgressUI(() => {
        this.showScanError(null, `Le scan en direct est indisponible (${err && err.name ? err.name : 'réseau'}). Un aperçu de démonstration est affiché — vérifiez que le service /api/scan répond puis réessayez.`, customUrl.trim());
        const fallbackData = { ...AUDIT_PRESETS['friction'] };
        fallbackData.domain = customUrl.trim();
        fallbackData.name = `Boutique : ${cleanDomain}`;
        fallbackData.productData = {
          name: `Article scanné (${cleanDomain})`,
          brand: cleanDomain,
          price: "À confirmer",
          currency: "EUR",
          description: `Analyse directe de la boutique ${cleanDomain}. Schéma partiel détecté.`,
          has_stock: false,
          has_shipping: false,
          has_return: false
        };
        fallbackData.summary = `Le site ${cleanDomain} est accessible mais certaines données structurées sont incomplètes.`;
        this.displayResults(fallbackData);
        this.isScanning = false;
      });
    }
  }

  hideScanError() {
    if (!this.errorBox) return;
    this.errorBox.style.display = 'none';
    this.errorBox.classList.remove('is-hard');
  }

  showScanError(status, message, url) {
    if (!this.errorBox) {
      console.warn('Bandeau d\'erreur absent du DOM, message ignoré :', message);
      return;
    }
    // Cache tout résultat précédent : on est dans un état d'erreur, pas un audit.
    if (this.resultsCard) this.resultsCard.classList.remove('active');
    const wafCard = document.getElementById('waf-blocked-card');
    if (wafCard) wafCard.style.display = 'none';

    // Titre contextuel selon la classe de statut.
    let hard = true;
    let title = 'Scan non effectué';
    if (status === 408 || status === null) { title = 'Scan indisponible'; hard = false; }
    else if (status === 429) { title = 'Trop de scans — patientez un instant'; }
    else if (status === 404) { title = 'Page introuvable'; }
    else if (status === 413) { title = 'Page trop volumineuse'; }
    else if (status === 415) { title = 'Ce n\'est pas une page web'; }

    if (this.errorTitle) this.errorTitle.textContent = title;
    if (this.errorMessage) this.errorMessage.textContent = message || 'L\'analyse n\'a pas pu aboutir.';
    this.errorBox.classList.toggle('is-hard', hard);
    this.errorBox.style.display = 'block';

    // Pré-remplit le lien de contact avec l'URL fautive pour un suivi simple.
    const subject = encodeURIComponent(`Demande d'aide : scan de ${url || 'un site'}`);
    if (this.errorContact) {
      this.errorContact.href = `mailto:contact@agentready.io?subject=${subject}`;
    }

    this.errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  startProgressUI() {
    this.resultsCard.classList.remove('active');
    this.progressBox.style.display = 'block';
    this.progressBar.style.width = '0%';
    this.stepsList.forEach(s => {
      s.classList.remove('active', 'done');
      const icon = s.querySelector('i');
      if (icon) icon.className = 'fas fa-circle-notch fa-spin';
    });

    // Animate first 3 steps while waiting for network
    setTimeout(() => {
      this.progressStatus.textContent = "1/5 Directives robots.txt & détection WAF...";
      this.progressBar.style.width = "20%";
      if (this.stepsList[0]) this.stepsList[0].classList.add('active');
    }, 100);

    setTimeout(() => {
      if (this.stepsList[0]) {
        this.stepsList[0].classList.replace('active', 'done');
        this.stepsList[0].querySelector('i').className = 'fas fa-check-circle';
      }
      this.progressStatus.textContent = "2/5 Extraction DOM & parsing Schema.org JSON-LD...";
      this.progressBar.style.width = "40%";
      if (this.stepsList[1]) this.stepsList[1].classList.add('active');
    }, 450);

    setTimeout(() => {
      if (this.stepsList[1]) {
        this.stepsList[1].classList.replace('active', 'done');
        this.stepsList[1].querySelector('i').className = 'fas fa-check-circle';
      }
      this.progressStatus.textContent = "3/5 Pureté sémantique & ratio signal/bruit...";
      this.progressBar.style.width = "60%";
      if (this.stepsList[2]) this.stepsList[2].classList.add('active');
    }, 850);

    setTimeout(() => {
      if (this.stepsList[2]) {
        this.stepsList[2].classList.replace('active', 'done');
        this.stepsList[2].querySelector('i').className = 'fas fa-check-circle';
      }
      this.progressStatus.textContent = "4/5 Simulateur d'achat IA (intention & checkout)...";
      this.progressBar.style.width = "80%";
      if (this.stepsList[3]) this.stepsList[3].classList.add('active');
    }, 1250);
  }

  completeProgressUI(callback) {
    this.progressBar.style.width = "100%";
    this.progressStatus.textContent = "5/5 Synthèse et génération des protocoles...";
    this.stepsList.forEach(s => {
      s.classList.remove('active');
      s.classList.add('done');
      const icon = s.querySelector('i');
      if (icon) icon.className = 'fas fa-check-circle';
    });

    setTimeout(() => {
      this.progressBox.style.display = 'none';
      try {
        if (callback) callback();
      } catch (err) {
        console.error("Erreur lors de l'affichage des résultats :", err);
      } finally {
        this.isScanning = false;
      }
    }, 350);
  }

  runScanWithPreset(presetKey) {
    if (this.isScanning) return;
    this.isScanning = true;

    const data = { ...AUDIT_PRESETS[presetKey] };

    this.startProgressUI();
    setTimeout(() => {
      this.completeProgressUI(() => {
        this.displayResults(data);
      });
    }, 1000);
  }

  displayResults(data) {
    if (!data) return;
    window.__lastAuditData = data;

    // Dégradation propre WAF / CSR (Task 4)
    const wafCard = document.getElementById('waf-blocked-card');
    const wafBlockerName = document.getElementById('waf-blocker-name');
    const btnRetryWaf = document.getElementById('btn-retry-waf-scan');

    if (btnRetryWaf) {
      btnRetryWaf.onclick = () => {
        const url = this.input ? this.input.value.trim() : '';
        this.runScan(url);
      };
    }

    if (data.isWafBlocked) {
      if (this.resultsCard) this.resultsCard.classList.remove('active');
      if (wafCard) {
        wafCard.style.display = 'block';
        if (wafBlockerName && data.wafDetails?.blocker) {
          wafBlockerName.textContent = data.wafDetails.blocker;
        }
        wafCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      return;
    } else {
      if (wafCard) wafCard.style.display = 'none';
    }

    try {
      if (this.domainTitle) this.domainTitle.textContent = data.name || 'Boutique E-commerce';
      if (this.domainUrl) this.domainUrl.textContent = data.domain || '';
      if (this.auditSummary) this.auditSummary.textContent = data.summary || 'Analyse terminée.';

      // Status Badge
      if (this.statusBadge) {
        this.statusBadge.className = `badge ${data.statusBadgeClass || 'badge-friction'}`;
        this.statusBadge.innerHTML = `<span class="pulse-dot"></span> ${data.statusLabel || 'En analyse'}`;
      }

      // Safe access to pillars
      const p = data.pillars || {};
      const crawl = p.crawl || { score: 0, status: '--' };
      const schema = p.schema || { score: 0, status: '--' };
      const tokens = p.tokens || { score: 0, status: '--' };
      const sim = p.simulator || { score: 0, status: '--' };
      const proto = p.proto || p.protocols || { score: 0, status: '--' };

      // Affichage instantané de la photo de l'article scanné sans stockage serveur
      const thumbWrapper = document.getElementById('audit-product-img-wrapper');
      const thumbImg = document.getElementById('audit-product-thumb');
      const prodImgUrl = data.image || data.productData?.image;

      if (thumbWrapper && thumbImg) {
        if (prodImgUrl) {
          thumbImg.src = prodImgUrl;
          thumbImg.onerror = () => {
            thumbWrapper.style.display = 'none';
          };
          thumbWrapper.style.display = 'block';
        } else {
          thumbWrapper.style.display = 'none';
        }
      }

      // Synchronisation complète de la VUE HUMAINE (Design & Branding)
      const humanProductImg = document.querySelector('.human-product-img');
      const humanTitle = document.getElementById('human-product-title') || document.querySelector('.human-title');
      const humanBrand = document.getElementById('human-product-brand');
      const humanPrice = document.getElementById('human-product-price');
      const humanDesc = document.getElementById('human-product-desc');

      if (humanProductImg) {
        if (prodImgUrl) {
          humanProductImg.src = prodImgUrl;
          humanProductImg.onerror = () => {
            humanProductImg.src = 'assets/product_human_view.jpg';
          };
        } else {
          humanProductImg.src = 'assets/product_human_view.jpg';
        }
      }

      const prodName = data.productData?.name || data.name || 'Produit E-commerce';
      if (humanTitle) humanTitle.textContent = prodName;

      const domainClean = (data.domain || '').replace(/^https?:\/\//, '').split('/')[0];
      const brandName = data.productData?.brand || domainClean || 'Boutique E-commerce';
      if (humanBrand) humanBrand.textContent = brandName;

      if (humanPrice) {
        const rawPrice = data.productData?.price;
        const currency = data.productData?.currency || 'EUR';
        let displayPrice = 'Prix affiché sur le site';
        if (rawPrice && rawPrice !== 'Inconnu' && rawPrice !== 'None') {
          displayPrice = `${rawPrice} ${currency}`;
        } else if (data.aiView?.extractedPrice && data.aiView.extractedPrice !== '--') {
          displayPrice = data.aiView.extractedPrice.split('(')[0].trim();
        }
        const isStockOk = Boolean(data.productData?.has_stock);
        humanPrice.textContent = '';
        humanPrice.appendChild(document.createTextNode(`${displayPrice} `));
        const stockSpan = document.createElement('span');
        stockSpan.style.fontSize = '0.9rem';
        stockSpan.style.color = isStockOk ? 'var(--emerald-400)' : 'var(--amber-400)';
        stockSpan.style.fontWeight = '600';
        stockSpan.textContent = isStockOk ? '• En Stock • Expédition 24h' : '• Stock à confirmer par l\'IA';
        humanPrice.appendChild(stockSpan);
      }

      if (humanDesc) {
        if (data.productData?.description && data.productData.description.length > 20) {
          humanDesc.textContent = data.productData.description.slice(0, 220) + (data.productData.description.length > 220 ? '...' : '');
        } else {
          humanDesc.textContent = `Fiche produit scannée en direct sur ${domainClean}. ` + (data.summary || '');
        }
      }

      if (this.crawlScore) this.crawlScore.textContent = `${crawl.score}/100`;
      if (this.crawlStatus) this.crawlStatus.textContent = crawl.status;

      if (this.schemaScore) this.schemaScore.textContent = `${schema.score}/100`;
      if (this.schemaStatus) this.schemaStatus.textContent = schema.status;

      if (this.tokensScore) this.tokensScore.textContent = `${tokens.score}/100`;
      if (this.tokensStatus) this.tokensStatus.textContent = tokens.status;

      if (this.simScore) this.simScore.textContent = `${sim.score}/100`;
      if (this.simStatus) this.simStatus.textContent = sim.status;

      const geminiPillarBadge = document.getElementById('pillar-gemini-badge');
      if (geminiPillarBadge) {
        if (data.geminiLive) {
          geminiPillarBadge.innerHTML = '<i class="fas fa-brain" style="color: #34d399;"></i> Gemini 3.6 Live';
          geminiPillarBadge.style.color = 'var(--emerald-400)';
        } else {
          geminiPillarBadge.innerHTML = '<i class="fas fa-microchip"></i> IA Déterministe';
          geminiPillarBadge.style.color = 'var(--cyan-400)';
        }
      }

      // Save audited product data for interactive simulator
      window.__currentAuditedProduct = data.productData || { name: data.name };
      window.dispatchEvent(new CustomEvent('agentready:product-updated', { detail: window.__currentAuditedProduct }));

      if (this.protoScore) this.protoScore.textContent = `${proto.score}/100`;
      if (this.protoStatus) this.protoStatus.textContent = proto.status;

      // Synchronisation complète de la VUE AGENT IA (Flux Brut & Schéma)
      const ai = data.aiView || {};
      const terminalName = document.getElementById('ai-inspect-name');
      const terminalPrice = document.getElementById('ai-inspect-price');
      const terminalStock = document.getElementById('ai-inspect-stock');
      const terminalShipping = document.getElementById('ai-inspect-shipping');
      const terminalTokens = document.getElementById('ai-inspect-tokens');
      const terminalPurity = document.getElementById('ai-inspect-purity');
      const terminalRisk = document.getElementById('ai-inspect-risk');
      const terminalBot = document.getElementById('ai-inspect-bot');
      const terminalVerdict = document.getElementById('ai-inspect-verdict');

      if (terminalName) terminalName.textContent = prodName;
      if (terminalPrice) terminalPrice.textContent = ai.extractedPrice || '--';
      
      if (terminalStock) {
        terminalStock.textContent = ai.stockStatus || '--';
        const isStockPositive = (ai.stockStatus || '').toLowerCase().includes('in_stock') || (ai.stockStatus || '').toLowerCase().includes('en stock');
        terminalStock.className = isStockPositive ? 'ai-tag-ok' : 'ai-tag-missing';
      }

      if (terminalShipping) {
        terminalShipping.textContent = ai.shippingTerms || '--';
        const isShippingPositive = (ai.shippingTerms || '').toLowerCase().includes('spécifiée') || (ai.shippingTerms || '').toLowerCase().includes('gratuite') || (ai.shippingTerms || '').toLowerCase().includes('validé');
        terminalShipping.className = isShippingPositive ? 'ai-tag-ok' : 'ai-tag-missing';
      }

      if (terminalBot) {
        terminalBot.textContent = ai.botAccess || '--';
        const isBotAllowed = (ai.botAccess || '').toLowerCase().includes('autoris');
        terminalBot.className = isBotAllowed ? 'ai-tag-ok' : 'ai-tag-missing';
      }

      if (terminalTokens) terminalTokens.textContent = ai.tokens || '--';
      if (terminalRisk) {
        terminalRisk.textContent = ai.hallucinationRisk || '--';
        const isRiskLow = (ai.hallucinationRisk || '').toLowerCase().includes('nul') || (ai.hallucinationRisk || '').toLowerCase().includes('faible');
        terminalRisk.style.color = isRiskLow ? 'var(--emerald-400)' : 'var(--rose-400)';
      }

      if (terminalPurity) {
        const noise = data.pillars?.tokens?.noise_pct ?? 78;
        const purity = Math.max(1, 100 - noise);
        terminalPurity.textContent = `${purity}% utile (Bruit: ${noise}%)`;
        terminalPurity.style.color = purity >= 30 ? 'var(--emerald-400)' : 'var(--amber-400)';
      }

      if (terminalVerdict) {
        terminalVerdict.textContent = '';
        const tagSpan = document.createElement('span');
        if (data.score >= 70) {
          tagSpan.className = 'ai-tag-ok';
          tagSpan.textContent = `CONFIRMÉ (Score: ${data.score}/100)`;
          terminalVerdict.appendChild(tagSpan);
          terminalVerdict.appendChild(document.createTextNode(` : Métadonnées certifiées pour "${prodName}", conversion IA favorable.`));
        } else {
          tagSpan.className = 'ai-tag-missing';
          tagSpan.textContent = `DISQUALIFIÉ (Score: ${data.score}/100)`;
          terminalVerdict.appendChild(tagSpan);
          terminalVerdict.appendChild(document.createTextNode(` : L'IA ne peut pas certifier l'achat autonome pour "${prodName}".`));
        }
      }

      // Populate What's Broken List (P0 Commando Feature)
      if (this.whatsBrokenList) {
        const items = data.brokenItems || [];
        if (this.brokenCountBadge) {
          const critCount = items.filter(i => i.severity === 'critical').length;
          this.brokenCountBadge.textContent = `${items.length} point${items.length > 1 ? 's' : ''} d'impact détecté${items.length > 1 ? 's' : ''}`;
          this.brokenCountBadge.style.color = critCount > 0 ? 'var(--rose-400)' : 'var(--emerald-400)';
        }

        this.whatsBrokenList.innerHTML = items.map(item => {
          const isCrit = item.severity === 'critical';
          const isWarn = item.severity === 'warning';
          const icon = isCrit ? 'fa-times-circle' : (isWarn ? 'fa-exclamation-triangle' : 'fa-check-circle');
          const color = isCrit ? 'var(--rose-400)' : (isWarn ? 'var(--amber-400)' : 'var(--emerald-400)');
          const itemClass = isCrit ? '' : (isWarn ? 'warning' : 'info');
          return `
            <div class="whats-broken-item ${itemClass}">
              <i class="fas ${icon} whats-broken-icon" style="color: ${color};"></i>
              <div class="whats-broken-content">
                <div class="whats-broken-title">${escapeHtml(item.title)}</div>
                <div class="whats-broken-impact">${escapeHtml(item.impact)}</div>
              </div>
            </div>
          `;
        }).join('');
      }

      // Populate Inline Auto-Fix (Before / After)
      this.setInlineMode('after');

      // Show Card
      if (this.resultsCard) {
        this.resultsCard.classList.add('active');
      }

      // Animate Gauge & Count Up
      this.animateGauge(data.score || 0);

      // Scroll to results smoothly
      if (this.resultsCard) {
        this.resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    } catch (err) {
      console.error("Erreur dans displayResults :", err);
    }
  }

  animateGauge(targetScore) {
    const circumference = 251.2; // 2 * pi * r (r = 40)
    const targetOffset = circumference - (circumference * targetScore) / 100;

    // Set color based on score
    if (targetScore >= 80) {
      this.gaugeCircle.style.stroke = 'var(--emerald-500)';
    } else if (targetScore >= 50) {
      this.gaugeCircle.style.stroke = 'var(--amber-500)';
    } else {
      this.gaugeCircle.style.stroke = 'var(--rose-500)';
    }

    this.gaugeCircle.style.strokeDashoffset = targetOffset;

    // Counter animation
    let count = 0;
    const duration = 1000;
    const stepTime = 20;
    const increment = targetScore / (duration / stepTime);

    const timer = setInterval(() => {
      count += increment;
      if (count >= targetScore) {
        this.scoreNumber.textContent = targetScore;
        if (this.headerScore) {
          this.headerScore.innerHTML = `${targetScore}<span style="font-size: 1rem; color: var(--text-muted);">/100</span>`;
        }
        clearInterval(timer);
      } else {
        const val = Math.floor(count);
        this.scoreNumber.textContent = val;
        if (this.headerScore) {
          this.headerScore.innerHTML = `${val}<span style="font-size: 1rem; color: var(--text-muted);">/100</span>`;
        }
      }
    }, stepTime);
  }
}
