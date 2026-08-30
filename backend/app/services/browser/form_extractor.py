"""JavaScript-based form extractor: runs in-page to extract form structure.

All DOM interaction is in JavaScript so the Python layer stays clean.
"""

# JavaScript that runs inside the page and returns form structure as JSON.
# Returns: list of field dicts with id, name, label, type, required, options, selector.
# Supports: standard inputs, custom comboboxes (aria role="combobox"), hidden file inputs,
# and basic shadow-DOM-surfaced elements reachable via composed tree queries.
FORM_EXTRACTOR_JS = """
() => {
  const form = document.querySelector('form') || document.body;

  function getLabel(el) {
    // 1. label[for=id]
    if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) return lbl.textContent.trim();
    }
    // 2. aria-label
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    // 3. aria-labelledby
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const ids = labelledby.split(' ');
      const parts = ids.map(id => {
        const el2 = document.getElementById(id);
        return el2 ? el2.textContent.trim() : '';
      }).filter(Boolean);
      if (parts.length) return parts.join(' ');
    }
    // 4. placeholder as fallback
    if (el.placeholder) return el.placeholder.trim();
    // 5. parent label
    if (el.closest('label')) return el.closest('label').textContent.replace(el.value || '', '').trim();
    // 6. nearest preceding element with text
    let prev = el.previousElementSibling;
    while (prev) {
      const txt = prev.textContent.trim();
      if (txt.length > 0 && txt.length < 120) return txt;
      prev = prev.previousElementSibling;
    }
    // 7. parent's label-like child (div/span before input inside same container)
    const parent = el.parentElement;
    if (parent) {
      const labelEl = parent.querySelector('label, .label, [class*="label"]');
      if (labelEl) return labelEl.textContent.trim();
    }
    return el.name || el.id || '';
  }

  function getSectionTitle(el) {
    const fieldset = el.closest('fieldset');
    if (fieldset) {
      const legend = fieldset.querySelector('legend');
      if (legend) return legend.textContent.trim();
    }
    const section = el.closest('section, [class*="section"], [class*="group"], [class*="panel"]');
    if (section) {
      const heading = section.querySelector('h1, h2, h3, h4, h5, h6');
      if (heading) return heading.textContent.trim();
    }
    return null;
  }

  function getCssSelector(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `[name="${CSS.escape(el.name)}"]`;
    // fallback: tag + index among siblings
    const siblings = Array.from(el.parentElement ? el.parentElement.children : []);
    const idx = siblings.indexOf(el);
    return `${el.tagName.toLowerCase()}:nth-child(${idx + 1})`;
  }

  function getOptions(el) {
    if (el.tagName === 'SELECT') {
      return Array.from(el.options)
        .filter(o => o.value !== '' && o.value !== null)
        .map(o => o.text.trim());
    }
    // Custom combobox: look for listbox children
    const role = el.getAttribute('role');
    if (role === 'combobox' || role === 'listbox') {
      const opts = el.querySelectorAll('[role="option"]');
      if (opts.length) return Array.from(opts).map(o => o.textContent.trim());
    }
    return null;
  }

  // Collect standard inputs
  const stdSelector = [
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"])',
    ':not([type="reset"]):not([type="image"])',
    ', select, textarea',
  ].join('');
  const inputs = Array.from(form.querySelectorAll(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]' +
    '):not([type="reset"]):not([type="image"]), select, textarea'
  ));

  // Also collect custom combobox containers (React/Vue select replacements)
  const comboboxes = Array.from(form.querySelectorAll(
    '[role="combobox"]:not(input), [role="listbox"]'
  ));

  // Also collect hidden file inputs (they are type=file but hidden via CSS)
  const hiddenFiles = Array.from(form.querySelectorAll(
    'input[type="file"]'
  )).filter(el => {
    const style = window.getComputedStyle(el);
    return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
  });

  const allEls = [...inputs, ...comboboxes, ...hiddenFiles];
  // Deduplicate by node identity
  const seen = new Set();
  const uniqueEls = allEls.filter(el => {
    if (seen.has(el)) return false;
    seen.add(el);
    return true;
  });

  const fields = uniqueEls.map((el, idx) => {
    const tagName = el.tagName;
    const role = el.getAttribute('role') || '';
    let fieldType;
    if (tagName === 'SELECT') fieldType = 'select';
    else if (tagName === 'TEXTAREA') fieldType = 'textarea';
    else if (role === 'combobox' || role === 'listbox') fieldType = 'custom_select';
    else fieldType = el.type || 'text';

    const isHidden = fieldType !== 'custom_select' && (() => {
      const s = window.getComputedStyle(el);
      return s.display === 'none' || s.visibility === 'hidden';
    })();

    return {
      field_id: el.id || el.name || `field_${idx}`,
      name: el.name || el.id || `field_${idx}`,
      label: getLabel(el),
      field_type: fieldType,
      is_required: el.required || el.getAttribute('aria-required') === 'true',
      options: getOptions(el),
      placeholder: el.placeholder || null,
      css_selector: getCssSelector(el),
      section_title: getSectionTitle(el),
      aria_label: el.getAttribute('aria-label') || null,
      is_hidden: isHidden,
    };
  });

  // Find submit button
  const submitBtn = form.querySelector(
    'button[type="submit"], input[type="submit"], button:not([type])'
  );
  const submitSelector = submitBtn && submitBtn.id
    ? `#${CSS.escape(submitBtn.id)}`
    : (submitBtn ? submitBtn.tagName.toLowerCase() + '[type="submit"]' : 'button[type="submit"]');

  // Extract sections from fieldsets / headings
  const sections = [];
  const fieldsetEls = form.querySelectorAll('fieldset');
  if (fieldsetEls.length > 0) {
    fieldsetEls.forEach(fs => {
      const legend = fs.querySelector('legend');
      sections.push({ title: legend ? legend.textContent.trim() : null });
    });
  }

  return {
    fields,
    page_title: document.title || null,
    submit_button_selector: submitSelector,
    form_action: (form.tagName === 'FORM' ? form.action : null) || null,
    sections: sections,
  };
}
"""

# JavaScript to detect common confirmation page patterns
# Raw string: backslashes pass through to JavaScript regex engine unchanged
CONFIRMATION_DETECTOR_JS = r"""
() => {
  const text = document.body.innerText.toLowerCase();
  const patterns = [
    'application submitted',
    'application received',
    'thank you for applying',
    'your application has been',
    'successfully submitted',
    'application reference',
    'confirmation number',
    'application id',
    'we have received your',
  ];
  const matched = patterns.some(p => text.includes(p));

  // Try to extract a confirmation ID / reference number
  const refPatterns = [
    /\b(app[-_][a-z0-9]{4,})\b/i,
    /\b(ref[-_:]?\s*[A-Z0-9]{6,})\b/i,
    /reference[:\s]+([A-Z0-9-]{4,})/i,
    /confirmation[:\s]+([A-Z0-9-]{4,})/i,
    /application\s+(?:id|number|#)[:\s]+([A-Z0-9-]{4,})/i,
  ];
  let confirmationId = null;
  for (const pattern of refPatterns) {
    const m = text.match(pattern);
    if (m) { confirmationId = m[1].trim(); break; }
  }

  return { is_confirmation: matched, confirmation_id: confirmationId, page_text: text.slice(0, 2000) };
}
"""
