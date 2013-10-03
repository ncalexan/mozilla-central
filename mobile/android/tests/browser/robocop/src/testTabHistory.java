package org.mozilla.gecko.robocop.tests;

public class testTabHistory extends BaseTest {

    @Override
    protected int getTestType() {
        return TEST_MOCHITEST;
    }

    /* This test will check the functionality of the Back, Forward and Reload buttons.
    First it will determine the Device and the OS.
    Then it will create the appropriate navigation mechanisms for back, forward and reload depending on device type and OS.
    Finally it will run the tests */

    public void testTabHistory() {
        blockForGeckoReady();

        String url = getAbsoluteUrl("/robocop/robocop_blank_01.html");
        String url2 = getAbsoluteUrl("/robocop/robocop_blank_02.html");
        String url3 = getAbsoluteUrl("/robocop/robocop_blank_03.html");

        // Create tab history
        inputAndLoadUrl(url);
        verifyPageTitle("Browser Blank Page 01");
        inputAndLoadUrl(url2);
        verifyPageTitle("Browser Blank Page 02");
        inputAndLoadUrl(url3);
        verifyPageTitle("Browser Blank Page 03");

        // Get the device information and create the navigation for it
        Navigation nav = new Navigation(mDevice);
        mAsserter.dumpLog("device type: "+mDevice.type);
        mAsserter.dumpLog("device version: "+mDevice.version);
        mAsserter.dumpLog("device width: "+mDevice.width);
        mAsserter.dumpLog("device height: "+mDevice.height);

        // Go to the 2nd page
        nav.back();
        waitForText("Browser Blank Page 02");
        verifyPageTitle("Browser Blank Page 02");

        // Go to the first page
        nav.back();
        waitForText("Browser Blank Page 01");
        verifyPageTitle("Browser Blank Page 01");

        // Go forward to the second page
        nav.forward();
        waitForText("Browser Blank Page 02");
        verifyPageTitle("Browser Blank Page 02");

        // Reload page
        nav.reload();
        waitForText("Browser Blank Page 02");
        verifyPageTitle("Browser Blank Page 02");
    }
}
