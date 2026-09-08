(function () {
    const normalize = (value) =>
        (value || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();

    const initZoneSearch = (select) => {
        const placeholder = select.dataset.zoneSearchPlaceholder || 'Rechercher une zone';
        const searchUrl = select.dataset.zoneSearchUrl;
        const providerId = select.dataset.zoneProviderId;
        const valueField = select.dataset.zoneValueField || 'id';
        const labelField = select.dataset.zoneLabelField || 'name';
        let searchController = null;

        const options = Array.from(select.options)
            .map((option) => ({
                value: option.value,
                label: option.textContent.trim(),
                disabled: option.disabled,
            }))
            .filter((option) => option.value !== '' && option.label);

        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = select.name;
        hiddenInput.value = select.value;
        hiddenInput.required = select.required;

        const wrapper = document.createElement('div');
        wrapper.className = 'zone-search';

        const textInput = document.createElement('input');
        textInput.type = 'search';
        textInput.placeholder = placeholder;
        textInput.autocomplete = 'off';
        textInput.className = 'zone-search__input';
        textInput.required = select.required;
        textInput.setAttribute('aria-label', 'Zone du rendez-vous');

        const dropdown = document.createElement('div');
        dropdown.className = 'zone-search__dropdown';
        dropdown.hidden = true;

        wrapper.appendChild(textInput);
        wrapper.appendChild(dropdown);
        wrapper.appendChild(hiddenInput);

        const selectedOption = select.options[select.selectedIndex];
        const hasSelectedValue = selectedOption && selectedOption.value !== '';
        if (hasSelectedValue) {
            textInput.value = selectedOption.textContent;
            hiddenInput.value = selectedOption.value;
        }

        select.name = '';
        select.required = false;
        select.removeAttribute('required');
        select.hidden = true;
        select.setAttribute('aria-hidden', 'true');
        select.after(wrapper);

        const closeDropdown = () => {
            dropdown.hidden = true;
            dropdown.innerHTML = '';
        };

        const syncValidity = () => {
            const hasSearchText = textInput.value.trim() !== '';
            textInput.setCustomValidity(
                hasSearchText && !hiddenInput.value
                    ? 'Sélectionne une zone dans la liste proposée.'
                    : ''
            );
        };

        const openDropdown = () => {
            dropdown.hidden = dropdown.children.length === 0;
        };

        const selectOption = (option) => {
            textInput.value = option.label;
            hiddenInput.value = option.value;
            syncValidity();
            closeDropdown();
        };

        const populateOptions = (results) => {
            dropdown.innerHTML = '';
            results.forEach((item) => {
                const option = document.createElement('button');
                option.type = 'button';
                option.className = 'zone-search__option';
                option.textContent = item.label;
                option.dataset.value = item.value;
                option.dataset.label = item.label;

                option.addEventListener('mousedown', (event) => {
                    event.preventDefault();
                    selectOption(item);
                });

                dropdown.appendChild(option);
            });
            openDropdown();
        };

        const filterOptions = (term = '') => {
            const normalizedTerm = normalize(term);
            const filtered = options
                .filter((option) => !option.disabled)
                .filter((option) => {
                    if (!normalizedTerm) return true;
                    return normalize(option.label).includes(normalizedTerm);
                })
                .slice(0, 20);
            populateOptions(filtered);
        };

        const searchOptions = async (term = '') => {
            if (!term.trim()) {
                closeDropdown();
                return;
            }
            if (!searchUrl) {
                filterOptions(term);
                return;
            }

            searchController?.abort();
            searchController = new AbortController();
            const url = new URL(searchUrl, window.location.origin);
            url.searchParams.set('q', term);
            if (providerId) url.searchParams.set('provider_id', providerId);

            try {
                const response = await window.fetch(url, {
                    headers: { Accept: 'application/json' },
                    signal: searchController.signal,
                });
                if (!response.ok) throw new Error('Zone search failed');
                const payload = await response.json();
                populateOptions((payload.results || []).map((item) => ({
                    value: item[valueField],
                    label: item[labelField],
                })));
            } catch (error) {
                if (error.name !== 'AbortError') filterOptions(term);
            }
        };

        textInput.addEventListener('input', (event) => {
            hiddenInput.value = '';
            syncValidity();
            searchOptions(event.target.value);
        });

        textInput.addEventListener('focus', () => {
            searchOptions(textInput.value);
        });

        textInput.addEventListener('blur', () => {
            const matchingOption = options.find((option) => normalize(option.label) === normalize(textInput.value));
            if (matchingOption && !matchingOption.disabled) {
                hiddenInput.value = matchingOption.value;
                textInput.value = matchingOption.label;
            }
            syncValidity();
            window.setTimeout(closeDropdown, 100);
        });

        textInput.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeDropdown();
            }
        });
    };

    document.addEventListener('DOMContentLoaded', () => {
        const zoneSelects = document.querySelectorAll('select[data-zone-search-url]');
        zoneSelects.forEach(initZoneSearch);
    });
})();
