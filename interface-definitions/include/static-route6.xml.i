<!-- included start from static-route6.xml.i -->
<tagNode name="route6">
  <properties>
    <help>VRF static IPv6 route</help>
    <valueHelp>
      <format>ipv6net</format>
      <description>VRF static IPv6 route</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-prefix"/>
    </constraint>
  </properties>
  <children>
    <node name="blackhole">
      <properties>
        <help>Silently discard pkts when matched</help>
      </properties>
      <children>
        #include <include/static-route-distance.xml.i>
      </children>
    </node>
    <tagNode name="interface">
      <properties>
        <help>IPv6 gateway interface name</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Gateway interface name</description>
        </valueHelp>
        <constraint>
          <regex>^(br|bond|dum|en|eth|gnv|peth|tun|vti|vxlan|wg|wlan)[0-9]+|lo$</regex>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static-route-distance.xml.i>
        #include <include/static-route-next-hop-vrf.xml.i>
      </children>
    </tagNode>
    <tagNode name="next-hop">
      <properties>
        <help>IPv6 gateway address</help>
        <valueHelp>
          <format>ipv6</format>
          <description>Next-hop IPv6 router</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static-route-distance.xml.i>
        #include <include/static-route-next-hop-interface.xml.i>
        #include <include/static-route-next-hop-vrf.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- included end -->

