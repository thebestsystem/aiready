/* ==========================================================================
   AGENTREADY - Main Application Orchestrator
   ========================================================================== */

import { ScannerSimulator } from './scanner-simulator.js?v=2.7';
import { SplitScreenViewer } from './split-screen.js?v=2.7';
import { SIMULATOR_QUESTIONS, CODE_SNIPPETS } from './mock-data.js?v=2.7';
import { BOOKING_URL, CHECKOUT_URL, CONTACT_EMAIL } from './config.js?v=2.7';

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Scanner & Split Viewer
  const scanner = new ScannerSimulator();
  const splitViewer = new SplitScreenViewer();

  // 2. Setup AI Buyer Simulator Tabs & Gemini
  initSimulatorTabs();

  // 3. Setup Gemini Configuration Modal
  initGeminiModal();

  // 4. Setup Auto-Fix Code Generator Tabs & Copy
  initCodeGenerator();

  // 5. Setup Pricing Toggle
  initPricingToggle();

  // 6. Setup PDF Report Modal & Real Download
  initPdfModal();

  // 6.5 Setup monetization CTAs (Calendly / Stripe checkout)
  initMonetizationCtas();

  // 7. Setup Share Audit Link
  initShareAudit();

  // 8. Setup FAQ Accordion
  initFaqAccordion();

  // 9. Setup Mobile Navigation Toggle
  initMobileNav();

  // 10. URL Deep Link (?url=...)
  const urlParams = new URLSearchParams(window.location.search);
  const sharedUrl = urlParams.get('url');

  if (sharedUrl) {
    const input = document.getElementById('scanner-url-input');
    if (input) input.value = sharedUrl;
    setTimeout(() => {
      scanner.runScan(sharedUrl);
    }, 400);
  }
});

/* --------------------------------------------------------------------------
   AI BUYER SIMULATOR INTERACTION (Google Gemini Flash)
   -------------------------------------------------------------------------- */
function initSimulatorTabs() {
  const simNav = document.getElementById('sim-nav-pills');
  const userPromptElem = document.getElementById('sim-user-prompt');
  
  // Standard Store elements
  const stdStatusElem = document.getElementById('sim-std-status');
  const stdResponseElem = document.getElementById('sim-std-response');
  const stdVerdictElem = document.getElementById('sim-std-verdict');

  // AgentReady Store elements
  const readyStatusElem = document.getElementById('sim-ready-status');
  const readyResponseElem = document.getElementById('sim-ready-response');
  const readyVerdictElem = document.getElementById('sim-ready-verdict');

  // Interactive Gemini question elements
  const customInput = document.getElementById('sim-custom-input');
  const askBtn = document.getElementById('btn-ask-gemini');
  const modelIndicator = document.getElementById('gemini-live-indicator-sim');
  const modelLabel = document.getElementById('sim-model-label');

  if (!simNav) return;

  // Render question pills
  simNav.innerHTML = SIMULATOR_QUESTIONS.map((q, idx) => `
    <button class="sim-pill ${idx === 0 ? 'active' : ''}" data-idx="${idx}">
      ${q.label}
    </button>
  `).join('');

  const pills = simNav.querySelectorAll('.sim-pill');

  const updateSimView = (index) => {
    const q = SIMULATOR_QUESTIONS[index];
    if (!q) return;

    pills.forEach((p, i) => p.classList.toggle('active', i === index));

    // Update dialogue texts
    userPromptElem.textContent = `"${q.userPrompt}"`;

    stdStatusElem.innerHTML = q.standardResponse.agentStatus;
    stdResponseElem.textContent = q.standardResponse.response;
    stdVerdictElem.innerHTML = `<strong>Impact :</strong> ${q.standardResponse.verdict}`;

    readyStatusElem.innerHTML = q.agentReadyResponse.agentStatus;
    readyResponseElem.textContent = q.agentReadyResponse.response;
    readyVerdictElem.innerHTML = `<strong>Impact :</strong> ${q.agentReadyResponse.verdict}`;
  };

  pills.forEach((pill, idx) => {
    pill.addEventListener('click', () => updateSimView(idx));
  });

  // Query Gemini live with custom question or on current audited product
  const askGeminiLive = async (questionText) => {
    if (!questionText || !questionText.trim()) return;

    pills.forEach(p => p.classList.remove('active'));
    userPromptElem.textContent = `"${questionText.trim()}"`;

    stdStatusElem.innerHTML = `<span class="pulse-dot"></span> Analyse en cours...`;
    stdResponseElem.textContent = `Google Gemini évalue le comportement de l'agent sur la page standard sans microdonnées...`;
    stdVerdictElem.innerHTML = `<strong>Impact :</strong> Évaluation de l'abandon de panier...`;

    readyStatusElem.innerHTML = `<span class="pulse-dot"></span> Analyse en cours...`;
    readyResponseElem.textContent = `Google Gemini évalue la réponse avec le protocole déterministe certifié...`;
    readyVerdictElem.innerHTML = `<strong>Impact :</strong> Validation du panier...`;

    try {
      const geminiKey = (localStorage.getItem('agentready_gemini_key') || '').trim();
      const payload = {
        question: questionText.trim(),
        productData: window.__currentAuditedProduct || null,
        geminiApiKey: geminiKey || undefined
      };

      const res = await fetch('/api/gemini/simulate-question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.standardResponse) {
        stdStatusElem.innerHTML = data.standardResponse.agentStatus || '⚠️ Incertitude';
        stdResponseElem.textContent = data.standardResponse.response || '--';
        stdVerdictElem.innerHTML = `<strong>Impact :</strong> ${data.standardResponse.verdict || ''}`;
      }

      if (data.agentReadyResponse) {
        readyStatusElem.innerHTML = data.agentReadyResponse.agentStatus || '✅ Déterministe';
        readyResponseElem.textContent = data.agentReadyResponse.response || '--';
        readyVerdictElem.innerHTML = `<strong>Impact :</strong> ${data.agentReadyResponse.verdict || ''}`;
      }

      if (modelLabel) {
        modelLabel.textContent = data.geminiLive ? 'Gemini 3.6 Flash (En direct)' : 'Mode Déterministe';
      }
      if (modelIndicator) {
        modelIndicator.className = data.geminiLive ? 'badge badge-ready' : 'badge badge-cyan';
      }

    } catch (err) {
      console.warn("Erreur requête simulateur :", err);
      stdStatusElem.innerHTML = '⚠️ Erreur simulateur';
      stdResponseElem.textContent = "Impossible de joindre le moteur Gemini local.";
      readyStatusElem.innerHTML = '✅ Mode Déterministe';
      readyResponseElem.textContent = "Les données certifiées de la fiche produit restent exploitables.";
    }
  };

  if (askBtn && customInput) {
    askBtn.addEventListener('click', () => {
      askGeminiLive(customInput.value);
    });
    customInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        askGeminiLive(customInput.value);
      }
    });
  }

  // Initial load
  updateSimView(0);
}

/* --------------------------------------------------------------------------
   CODE GENERATOR TABS & ACTIONS
   -------------------------------------------------------------------------- */
function initCodeGenerator() {
  const tabs = document.querySelectorAll('.code-tab-btn');
  const codeBlock = document.getElementById('code-display-block');
  const copyBtn = document.getElementById('btn-copy-code');
  const downloadBtn = document.getElementById('btn-download-code');
  
  let currentKey = 'llmsTxt';

  // Listen for real backend scan results to update code snippets in real-time
  window.addEventListener('agentready:scan-complete', (e) => {
    const realAutoFix = e.detail?.autoFix;
    if (realAutoFix) {
      if (realAutoFix.llmsTxt) CODE_SNIPPETS.llmsTxt = realAutoFix.llmsTxt;
      if (realAutoFix.schemaJson) CODE_SNIPPETS.schemaJson = realAutoFix.schemaJson;
      if (realAutoFix.mcpConfig) CODE_SNIPPETS.mcpConfig = realAutoFix.mcpConfig;
      updateCode(currentKey);
    }
  });

  const updateCode = (key) => {
    currentKey = key;
    tabs.forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === key));
    if (codeBlock && CODE_SNIPPETS[key]) {
      codeBlock.textContent = CODE_SNIPPETS[key];
    }
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const key = tab.getAttribute('data-tab');
      updateCode(key);
    });
  });

  // Copy to clipboard
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      const content = CODE_SNIPPETS[currentKey];
      try {
        await navigator.clipboard.writeText(content);
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="fas fa-check"></i> Copié !';
        copyBtn.style.color = 'var(--emerald-400)';
        setTimeout(() => {
          copyBtn.innerHTML = originalText;
          copyBtn.style.color = '';
        }, 2000);
      } catch (err) {
        console.error('Clipboard copy failed', err);
      }
    });
  }

  // Download File
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const content = CODE_SNIPPETS[currentKey];
      let filename = 'llms.txt';
      if (currentKey === 'schemaJson') filename = 'schema-product.json';
      if (currentKey === 'mcpConfig') filename = 'agentready-mcp.json';

      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Initial code
  updateCode('llmsTxt');
}

/* --------------------------------------------------------------------------
   PRICING BILLING TOGGLE
   -------------------------------------------------------------------------- */
function initPricingToggle() {
  const toggle = document.getElementById('pricing-billing-toggle');
  const pricePro = document.getElementById('price-pro');
  const priceAgency = document.getElementById('price-agency');

  if (!toggle) return;

  toggle.addEventListener('change', () => {
    if (toggle.checked) {
      // Annual (-20%)
      if (pricePro) pricePro.innerHTML = '39 € <span class="pricing-period">/ mois (facturé annuellement)</span>';
      if (priceAgency) priceAgency.innerHTML = '159 € <span class="pricing-period">/ mois (facturé annuellement)</span>';
    } else {
      // Monthly
      if (pricePro) pricePro.innerHTML = '49 € <span class="pricing-period">/ mois</span>';
      if (priceAgency) priceAgency.innerHTML = '199 € <span class="pricing-period">/ mois</span>';
    }
  });
}

/* --------------------------------------------------------------------------
   MODAL LEAD CAPTURE (PDF AUDIT & REAL DOWNLOAD)
   -------------------------------------------------------------------------- */
function initPdfModal() {
  const modal = document.getElementById('pdf-report-modal');
  const openBtns = document.querySelectorAll('.trigger-pdf-modal');
  const closeBtn = document.getElementById('modal-close-x');
  const modalFormContainer = document.getElementById('modal-lead-form');
  const modalForm = modalFormContainer ? (modalFormContainer.querySelector('form') || modalFormContainer) : null;
  const modalSuccess = document.getElementById('modal-success-state');
  const emailInput = document.getElementById('lead-email-input');

  if (!modal) return;

  const openModal = () => {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    if (modalFormContainer) modalFormContainer.style.display = 'block';
    if (modalSuccess) modalSuccess.style.display = 'none';
  };

  const closeModal = () => {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  };

  openBtns.forEach(btn => btn.addEventListener('click', openModal));
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  if (modalForm) {
    modalForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = emailInput ? emailInput.value.trim() : '';
      if (!email) return;
      const consentInput = document.getElementById('lead-consent-input');
      const consent = consentInput ? consentInput.checked : false;

      const submitBtn = modalForm.querySelector('button[type="submit"]');
      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Génération du PDF & enregistrement...';
      }

      try {
        const auditData = window.__lastAuditData || {
          domain: document.getElementById('scanner-url-input')?.value || 'https://mon-ecommerce.com',
          name: 'Boutique E-commerce',
          score: 34,
          statusLabel: 'IA BLIND',
          statusBadgeClass: 'badge-blind',
          pillars: {
            crawl: { score: 20, status: 'Critique' },
            schema: { score: 15, status: 'Inexistant' },
            tokens: { score: 35, status: 'Saturé' },
            simulator: { score: 25, status: 'Refus' },
            proto: { score: 0, status: 'Absent' }
          },
          summary: 'Audit généré depuis AgentReady Scanner.'
        };

        const res = await fetch('/api/report/pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: email,
            auditData: auditData,
            consent: consent
          })
        });

        if (!res.ok) {
          throw new Error(`Erreur HTTP ${res.status}`);
        }

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;
        const cleanDomain = (auditData.domain || 'audit').replace(/^https?:\/\//, '').replace(/[^a-zA-Z0-9.-]/g, '_');
        a.download = `AgentReady-Audit-${cleanDomain}.pdf`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          window.URL.revokeObjectURL(downloadUrl);
          a.remove();
        }, 1000);

        // Switch to success state
        if (modalFormContainer) modalFormContainer.style.display = 'none';
        if (modalSuccess) {
          modalSuccess.style.display = 'block';
          const userEmailSpan = document.getElementById('lead-sent-email');
          if (userEmailSpan) userEmailSpan.textContent = email;
        }

      } catch (err) {
        console.error('Erreur génération PDF :', err);
        alert(`Échec de la génération du rapport (${err.message}). Veuillez vérifier votre connexion et réessayer.`);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }
}

/* --------------------------------------------------------------------------
   MONETIZATION CTAs (Calendly / Stripe)
   -------------------------------------------------------------------------- */
function initMonetizationCtas() {
  const proBtn = document.getElementById('btn-pro-cta');

  const openOrMail = (url, fallbackSubject) => {
    if (url) {
      window.open(url, '_blank', 'noopener');
    } else {
      window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(fallbackSubject)}`;
    }
  };

  // Pro Merchant : Stripe checkout si configuré, sinon booking, sinon email.
  if (proBtn) {
    proBtn.addEventListener('click', () => {
      openOrMail(CHECKOUT_URL || BOOKING_URL, 'Essai Pro Merchant - AgentReady');
    });
  }

  // Le CTA Agence pointe désormais vers /agences (lien direct dans index.html).
}

/* --------------------------------------------------------------------------
   SHAREABLE AUDIT LINK (?url=...)
   -------------------------------------------------------------------------- */
function initShareAudit() {
  const shareBtn = document.getElementById('btn-share-audit');
  if (!shareBtn) return;

  shareBtn.addEventListener('click', async () => {
    const input = document.getElementById('scanner-url-input');
    const domain = window.__lastAuditData?.domain || (input ? input.value.trim() : '') || 'https://mystore-fashion.com';
    const cleanUrl = domain.startsWith('http') ? domain : `https://${domain}`;

    // Build URL with query parameter
    const shareUrl = new URL(window.location.origin + window.location.pathname);
    shareUrl.searchParams.set('url', cleanUrl);

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(shareUrl.toString());
      } else {
        const tempInput = document.createElement('input');
        tempInput.value = shareUrl.toString();
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        tempInput.remove();
      }

      const originalHtml = shareBtn.innerHTML;
      shareBtn.innerHTML = '<i class="fas fa-check" style="color: var(--emerald-400);"></i> Lien copié !';
      shareBtn.style.borderColor = 'var(--emerald-500)';
      shareBtn.style.color = 'var(--emerald-400)';
      
      setTimeout(() => {
        shareBtn.innerHTML = originalHtml;
        shareBtn.style.borderColor = '';
        shareBtn.style.color = '';
      }, 2500);

    } catch (err) {
      console.error("Erreur copie lien :", err);
      prompt("Copiez ce lien pour partager cet audit :", shareUrl.toString());
    }
  });
}

/* --------------------------------------------------------------------------
   FAQ ACCORDION
   -------------------------------------------------------------------------- */
function initFaqAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    if (questionBtn) {
      questionBtn.addEventListener('click', () => {
        const isOpen = item.classList.contains('active');
        faqItems.forEach(i => i.classList.remove('active'));
        if (!isOpen) {
          item.classList.add('active');
        }
      });
    }
  });
}

/* --------------------------------------------------------------------------
   GEMINI CONFIGURATION & STATUS MODAL
   -------------------------------------------------------------------------- */
function initGeminiModal() {
  const openBtn = document.getElementById('btn-open-gemini-modal');
  const modal = document.getElementById('gemini-modal');
  const closeBtn = document.getElementById('gemini-modal-close-x');
  const form = document.getElementById('gemini-key-form');
  const input = document.getElementById('gemini-key-input');
  const clearBtn = document.getElementById('btn-clear-gemini-key');
  const feedback = document.getElementById('gemini-test-feedback');
  const navStatus = document.getElementById('gemini-nav-status');
  const statusText = document.getElementById('gemini-status-text');

  if (!modal) return;

  const openModal = () => {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    checkStatus();
  };

  const closeModal = () => {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  };

  if (openBtn) openBtn.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  // Preload saved key
  const savedKey = localStorage.getItem('agentready_gemini_key') || '';
  if (input && savedKey) {
    input.value = savedKey;
  }

  const checkStatus = async () => {
    try {
      const res = await fetch('/api/gemini/status');
      if (res.ok) {
        const data = await res.json();
        const currentSavedKey = localStorage.getItem('agentready_gemini_key') || '';
        const hasKey = Boolean(currentSavedKey || data.serverKeyConfigured);
        if (hasKey) {
          if (navStatus) navStatus.textContent = 'Gemini 3.6 Actif';
          if (statusText) {
            statusText.className = 'badge badge-ready';
            statusText.innerHTML = '<span class="pulse-dot"></span> ' + (data.serverKeyConfigured ? 'Prêt (.env)' : 'Prêt (Clé locale)');
          }
        } else {
          if (navStatus) navStatus.textContent = 'Gemini IA';
          if (statusText) {
            statusText.className = 'badge badge-blind';
            statusText.innerHTML = '<span class="pulse-dot"></span> Mode Déterministe (Pas de clé)';
          }
        }
      }
    } catch (e) {
      if (navStatus) navStatus.textContent = 'Gemini Hors-Ligne';
      if (statusText) {
        statusText.className = 'badge badge-friction';
        statusText.textContent = 'Serveur injoignable';
      }
    }
  };

  // Check immediately on page load
  checkStatus();

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const key = input ? input.value.trim() : '';
      if (!key) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(244, 63, 94, 0.15)';
        feedback.style.color = 'var(--rose-400)';
        feedback.innerHTML = '⚠️ Veuillez entrer une clé API Google Gemini valide.';
        return;
      }

      feedback.style.display = 'block';
      feedback.style.background = 'rgba(59, 130, 246, 0.15)';
      feedback.style.color = 'var(--cyan-400)';
      feedback.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Test de connexion à Gemini 3.6 Flash en cours...';

      try {
        const res = await fetch('/api/gemini/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ geminiApiKey: key })
        });
        const data = await res.json();
        if (data.ok) {
          localStorage.setItem('agentready_gemini_key', key);
          feedback.style.background = 'rgba(16, 185, 129, 0.15)';
          feedback.style.color = 'var(--emerald-400)';
          feedback.innerHTML = '✅ Connexion réussie avec Google Gemini (modèle <code>gemini-3.6-flash</code>) !';
          checkStatus();
        } else {
          feedback.style.background = 'rgba(244, 63, 94, 0.15)';
          feedback.style.color = 'var(--rose-400)';
          feedback.innerHTML = `❌ Échec du test : ${data.error || 'Clé API non reconnue par Google GenAI'}`;
        }
      } catch (err) {
        feedback.style.background = 'rgba(244, 63, 94, 0.15)';
        feedback.style.color = 'var(--rose-400)';
        feedback.innerHTML = `❌ Erreur réseau : impossible de joindre le serveur d'API.`;
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      localStorage.removeItem('agentready_gemini_key');
      if (input) input.value = '';
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(245, 158, 11, 0.15)';
        feedback.style.color = 'var(--amber-400)';
        feedback.textContent = 'Clé locale effacée.';
      }
      checkStatus();
    });
  }
}

/* --------------------------------------------------------------------------
   MOBILE NAVIGATION TOGGLE (Accessible with Escape & Outside Click)
   -------------------------------------------------------------------------- */
function initMobileNav() {
  const toggleBtn = document.getElementById('btn-nav-toggle');
  const navMenu = document.getElementById('main-nav-menu');
  const geminiModal = document.getElementById('gemini-modal');
  const mobileGeminiBtn = document.getElementById('btn-open-gemini-modal-mobile');

  const closeMenu = () => {
    if (!navMenu || !navMenu.classList.contains('mobile-open')) return;
    navMenu.classList.remove('mobile-open');
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', 'false');
      const icon = toggleBtn.querySelector('i');
      if (icon) icon.className = 'fas fa-bars';
    }
  };

  const openMenu = () => {
    if (!navMenu) return;
    navMenu.classList.add('mobile-open');
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', 'true');
      const icon = toggleBtn.querySelector('i');
      if (icon) icon.className = 'fas fa-times';
    }
  };

  if (toggleBtn && navMenu) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = navMenu.classList.contains('mobile-open');
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    navMenu.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', () => {
        closeMenu();
      });
    });

    // Close mobile menu on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && navMenu.classList.contains('mobile-open')) {
        closeMenu();
        toggleBtn.focus();
      }
    });

    // Close when clicking outside navbar
    document.addEventListener('click', (e) => {
      if (navMenu.classList.contains('mobile-open') && !navMenu.contains(e.target) && !toggleBtn.contains(e.target)) {
        closeMenu();
      }
    });
  }

  if (mobileGeminiBtn && geminiModal) {
    mobileGeminiBtn.addEventListener('click', () => {
      geminiModal.classList.add('active');
      document.body.style.overflow = 'hidden';
      closeMenu();
    });
  }
}
