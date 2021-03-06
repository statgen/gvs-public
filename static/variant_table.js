window.is_gene = typeof window.transcripts_in_gene != 'undefined';

$(document).ready(function() {
    $('.consequence_display_buttons').change(function () {
        setTimeout(update_variants, 10);
    });
});

function add_tablesorter_csq_parser() {
    // Make a map of consequence -> index
    // That'll be the actual sort key, so lower i => more severe consequence
    var csq_order_index = {};
    _.each(window.csq_order, function(c, i) {
        csq_order_index[c] = i;
    });

    // Here we add a new sort parser - its global identifier is 'consequence'
    $.tablesorter.addParser({
        id: 'consequence',
        is: function(s) {
            return false;  // don't auto-detect parser
        },
        // this is the actual
        format: function(s, table, cell) {
            // I added the "original" VEP consequence as a data attribute to the table cell
            // This is what we use to look up the consequence order
            var original_csq = $(cell).data('consequence');
            return csq_order_index[original_csq];
        },
        type: 'numeric'
    });
}
add_tablesorter_csq_parser();


function add_tablesorter_formatted_number_parser() {
    // Here we add a new sort parser - its global identifier is pos'
    $.tablesorter.addParser({
        id: 'formatted_number',
        is: function(s) {
            return false;  // don't auto-detect parser
        },
        format: function(s, table, cell) {
            return $(cell).data('pos');
        },
        type: 'numeric'
    });
}
add_tablesorter_formatted_number_parser();


$(document).ready(function() {
    build_variant_table();
});

function build_variant_table() {

    $("#variants_loading").hide();
    $("#variants_table_container").show();
    window.variants_template = _.template($('#variant-table-template').html());
    $('#variants_table_container').html(variants_template({table_variants: table_variants}));
    $("#variant_table").tablesorter({
        sortList: [[9,0], [10,1]],
        // Here's where we tell tablesorter to use our new consequence sorter on the 9th column
        // 2-minute minor on Konrad for having hidden columns
        headers: {
            1: {sorter: 'formatted_number'},
            9: {sorter: 'consequence'}
        }
    });
        $('#pager').hide();

    function get_af_category(d) {
        if (!d.allele_freq) {
            return [0, '0'];
        } else if (d.allele_count == 1) {
            return [1, 'a singleton'];
        } else if (d.allele_freq < 1/10000) {
            return [2, '<1/10000'];
        } else if (d.allele_freq < 1/1000) {
            return [3, '1/10000-0.001'];
        } else if (d.allele_freq < 1/100) {
            return [4, '0.001-0.01'];
        } else if (d.allele_freq < 1/20) {
            return [5, '0.01-0.05'];
        } else if (d.allele_freq < 1/2) {
            return [6, '0.05-0.5'];
        } else {
            return [7, '0.5-1'];
        }
    }

    var data = window.table_variants;

    var width = 50;
    var height = 15;

    var x_scale = d3.scale.linear()
        .domain([0, 7])
        .range([0, width]);

    var svg;
    $.each(data, function(i, d) {
        d3.select('#variant_af_box_' + d.variant_id).attr("data-tooltip", "Shows allele frequency \n on a discrete " +
                "scale: \n singletons, <1/10,000, \n <1/1000, <1%, <5%, \n <50%, >50%. \n This particular variant is \n " +
                get_af_category(d)[1] + ".");
        svg = d3.select('#variant_af_box_' + d.variant_id)
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g");

        for (var j=0; j<8; j++) {
            svg.append('rect')
                    .style('stroke', 'steelblue')
                    .style('fill', 'white')
                    .attr('x', x_scale(j))
                    .attr('y', 0)
                    .attr('height', height)
                    .attr('width', x_scale(1) - x_scale(0))
        }

        svg.append('rect')
            .style('fill', 'steelblue')
            .attr('x', 0)
            .attr('y', 0)
            .attr('width', function() {
                return x_scale(get_af_category(d)[0]);
            })
            .attr('height', height);

    });
    update_variants();
    $("#export_to_csv").on('click', function (event) {
        var output_name = window.page_name === undefined ? 'export' : window.page_name;
        var timestamp = date_format(new Date());
        exportTableToCSV.apply(this, [$('#variant_table'), window.dataset_name + '_' + output_name + '_' + timestamp + '.csv']);
    });
}

function pad_2(number) { return (number < 10 ? '0' : '') + number; }

function date_format(date) {
    return date.getFullYear() + '_' +
        pad_2(date.getMonth()+1) + '_' +
        pad_2(date.getDate()) + '_' +
        pad_2(date.getHours()) + '_' +
        pad_2(date.getMinutes()) + '_' +
        pad_2(date.getSeconds()) ;
}

// Adapted from http://jsfiddle.net/terryyounghk/KPEGU/
function exportTableToCSV($table, filename) {

    var $rows = $table.find('tr:has(td,th)[style!="display: none;"]'),

        // Temporary delimiter characters unlikely to be typed by keyboard
        // This is to avoid accidentally splitting the actual contents
        tmpColDelim = String.fromCharCode(11), // vertical tab character
        tmpRowDelim = String.fromCharCode(0), // null character

        // actual delimiter characters for CSV format
        colDelim = '","',
        rowDelim = '"\r\n"',

        // Grab text from table into CSV formatted string
        csv = '"' + $rows.map(function (i, row) {
            var $row = $(row),
                $cols = $row.find('td,th').not('.omit_csv');

            return $cols.map(function (j, col) {
                var $col = $(col),
                    text = $col.text();

                return text.replace('"', '""').replace(/\s+/g, " ").replace(/^\s+/, "").replace(/\s+$/, ""); // escape double quotes

            }).get().join(tmpColDelim);

        }).get().join(tmpRowDelim)
            .split(tmpRowDelim).join(rowDelim)
            .split(tmpColDelim).join(colDelim) + '"',

        // Data URI
        csvData = 'data:application/csv;charset=utf-8,' + encodeURIComponent(csv);

    $(this)
        .attr({
        'download': filename,
            'href': csvData,
            'target': '_blank'
    });
}
