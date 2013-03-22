#!/usr/bin/perl

use  strict;
use File::Spec;

my $outdir = "@_REPLACE_MOZ_SRC_DIR@";
my $pkg = "@_REPLACE_PACKAGE_NAME@";
my @pkgsplit = split(/\./, $pkg);
my $pkgname = @pkgsplit[-1];

my $infiles = `find res/ -type f`;
while ($infiles=~/^(.*)$/gm) {
    my $infile = $1;
    chomp($infile);
    my $outfile = "$outdir/$infile";
    $outfile =~ s|/res/|/resources/|;

    open(my $fh, '<', $infile) or die $!;
    if (my $line = <$fh>) {
        chomp($line);
        if ($line ne "<!--gen-presource-->") {
            if (not stat($outfile)) {
                # file was created in eclipse; add it to working tree
                system("cp $infile $outfile");
            }
            next;
        }
    }

    open(my $out, '>', "$outfile.in") or die $!;

    while (<$fh>) {
        my $line = $_;
        if ($line =~ /^<!--gen-preproc:(.*)-->/) {
            $line = "$1\n";
        }
        $line =~ s/$pkg/\@ANDROID_PACKAGE_NAME@/g;

        print $out $line;
    }
    close($fh);
    close($out);
}


sub copy_new_file {
    my $infile = $_[0];
    my $file = $_[1];

    my $existing = `find $outdir -name $file`;
    chomp $existing;
    if (length $existing == 0) {
        # file was created in eclipse; add it to working tree
        my $outfile = "$outdir/$file";
        system("cp $infile $outfile");
    }
}

my $infiles = `find src/org/mozilla/gecko src/org/mozilla/$pkgname -name "*.java" -not -wholename "*/sync/*"`;
while ($infiles=~/^(.*)$/gm) {
    my $infile = $1;
    chomp($infile);
    my ($volume,$directories,$file) = File::Spec->splitpath($infile);

    open(my $fh, '<', $infile) or die $!;
    if (my $line = <$fh>) {
        chomp($line);
        if ($line ne "//gen-presource") {
            copy_new_file($infile, $file);
            next;
        }
    }

    my $outfile = `find $outdir -name $file.in`;
    chomp($outfile);
    if (length $outfile == 0) {
        copy_new_file($infile, "$file.in");
        next;
    }
    open(my $out, '>', $outfile) or die $!;

    my $skip = 0;
    while (<$fh>) {
        if ($skip == 1) {
            $skip = 0;
            next;
        }

        my $line = $_;
        if ($line =~ /^\/\/gen-preproc:(.*)/) {
            $line = "$1\n";
        } elsif ($line =~ /^\/\/gen-var:(.*)/) {
            $line = "$1\n";
            $skip = 1;
        }

        print $out $line;
    }
    close($fh);
    close($out);
}
