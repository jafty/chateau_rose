(function () {
    const debounce = (fn, delay = 250) => {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    };

    const initZoneSearch = (select) => {
        const searchUrl = select.dataset.zoneSearchUrl;
        if (!searchUrl) return;

        const labelField = select.dataset.zoneLabelField || 'name';
        const valueField = select.dataset.zoneValueField || 'id';
        const placeholder = select.dataset.zoneSearchPlaceholder || 'Rechercher une zone';

        const allowedValues = Array.from(select.options)
            .map((option) => option.value)
            .filter((value) => value !== '');

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

        const populateOptions = (results) => {
            dropdown.innerHTML = '';
            results.forEach((item) => {
                const option = document.createElement('button');
                const label = item[labelField] ?? '';
                const value = item[valueField] ?? '';
                option.type = 'button';
                option.className = 'zone-search__option';
                option.textContent = label;
                option.dataset.value = value;
                option.dataset.label = label;
                option.addEventListener('click', () => {
                    textInput.value = label;
                    hiddenInput.value = value || label;
                    closeDropdown();
                });
                dropdown.appendChild(option);
            });
            openDropdown();
        };

        const fetchResults = debounce((term) => {
            const url = new URL(searchUrl, window.location.origin);
            if (term) {
                url.searchParams.set('q', term);
            }
            fetch(url.toString(), { headers: { Accept: 'application/json' } })
                .then((response) => response.json())
                .then((data) => {
                    const results = Array.isArray(data.results) ? data.results : [];
                    const filteredResults = allowedValues.length
                        ? results.filter((item) => allowedValues.includes(String(item[valueField] ?? '')))
                        : results;
                    populateOptions(filteredResults);
                })
                .catch(() => {
                    closeDropdown();
                });
        }, 250);

        textInput.addEventListener('input', (event) => {
            hiddenInput.value = '';
            fetchResults(event.target.value.trim());
            dropdown.hidden = false;
        });

        textInput.addEventListener('change', () => {
            const match = Array.from(dropdown.children).find((option) => option.dataset.label === textInput.value);
            hiddenInput.value = match ? match.dataset.value || match.dataset.label : '';
            closeDropdown();
        });

        textInput.addEventListener('focus', () => {
            if (dropdown.children.length) {
                dropdown.hidden = false;
            } else {
                fetchResults(textInput.value.trim());
            }
        });

        document.addEventListener('click', (event) => {
            if (!wrapper.contains(event.target)) {
                closeDropdown();
            }
        });

        fetchResults('');
    };

    document.addEventListener('DOMContentLoaded', () => {
        const zoneSelects = document.querySelectorAll('select[data-zone-search-url]');
        zoneSelects.forEach(initZoneSearch);
    });
})();
