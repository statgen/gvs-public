function update_variants() {
    var category_buttons = $('.consequence_display_buttons.active');
    if (category_buttons.length === 1) {
        var category = category_buttons.attr('id').replace('consequence_', '').replace('_variant_button', '');
        $('[category]').hide();
        if (category == 'other') {
            $('[category]').show();
        } else if (category == 'missense') {
            $('[category=missense_variant]').show();
        }
        $('[category=lof_variant]').show();
        if ($('tr[style!="display: none;"]').length == 1) {
            $('#variants_table_empty').show();
            $('#variants_table_container').hide();
        } else {
            $('#variants_table_empty').hide();
            $('#variants_table_container').show();
        }
    }
    $(document).trigger("just_updated_variants");
}

function get_af_bounds(data) {
    // Removing AC_Adj = 0 cases
    var min_af = d3.min(data, function(d) {
        if (d.allele_freq > 0) {
            return d.allele_freq;
        } else {
            return 1;
        }
    });
    // Should this be 1?
    var max_af = d3.max(data, function(d) { return d.allele_freq; });
    return [min_af, max_af];
}

function with_waiting_notice(f) {
    $('body').css('cursor', 'progress');
    $("#wait-modal").modal({"backdrop": "static"});
    setTimeout(function() {
        f();
        $('body').css('cursor', 'default');
        $("#wait-modal").modal('hide');
    }, 10);
}

(function() {
    var autocomplete_bloodhound = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        identify: function(sugg) { return sugg.value; }, // maybe allows Bloodhound to `.get()`  objects
        remote: {
            url: '/api/autocomplete?query=%QUERY',
            wildcard: '%QUERY',
            rateLimitBy: 'throttle',
            rateLimitWait: 500,
            transform: function(data) {
                // Probably this function reveals that I don't understand Bloodhound.
                // But, I want my previous results to stay around while I keep typing.
                // If the string that's currently in the searchbox matches some string that's been suggested before, I want to see it!
                // This especially happens while I'm typing a chrom-pos-ref-alt.  If what I'm typing agrees with something being suggested, it shouldn't disappear!
                // So, I'm just adding everything to the local index. (Note: NOT localstorage.)
                // Bloodhound appears to perform deduping.
                autocomplete_bloodhound.add(data);
                return data;
            },
        },
        sorter: function(a, b) { return (a.value > b.value) ? 1 : -1; },
    });
    autocomplete_bloodhound.initialize();

    $(function() {
        $('.typeahead').typeahead({
            hint: false,
            highlight: true,
            minLength: 1,
        }, {
            name: 'autocomplete',
            source: autocomplete_bloodhound,
            display: 'value',
            limit: 10,
            templates: {
                suggestion: _.template("<div><%= value %></div>"),
                // Currently, variants and rsids do not give autocomplete results.
                // So, if `empty` is enabled, then they always say "No matches found", even though there ARE matches.
                // So, I'm removing this.  A bad solution, but better than nothing.
                //empty: "<div class='tt-empty-message'>No matches found.</div>"
            }
        });

        $('.typeahead').bind('typeahead:select', function(ev, suggestion) {
            window.location.href = '/awesome?query=' + suggestion.value;
        });
    });
})();


// convenience functions
function fmt(format) {
    var args = Array.prototype.slice.call(arguments, 1);
    return format.replace(/{(\d+)}/g, function(match, number) {
        return (typeof args[number] != 'undefined') ? args[number] : match;
    });
}
