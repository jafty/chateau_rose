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

        const openDropdown = () => {
            dropdown.hidden = dropdown.children.length === 0;
        };

        const selectOption = (option) => {
            textInput.value = option.label;
            hiddenInput.value = option.value;
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

        textInput.addEventListener('input', (event) => {
            hiddenInput.value = '';
            filterOptions(event.target.value);
            dropdown.hidden = false;
        });

        textInput.addEventListener('focus', () => {
            filterOptions(textInput.value);
        });

        textInput.addEventListener('blur', () => {
            const matchingOption = options.find((option) => normalize(option.label) === normalize(textInput.value));
            if (matchingOption && !matchingOption.disabled) {
                hiddenInput.value = matchingOption.value;
                textInput.value = matchingOption.label;
            }
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
